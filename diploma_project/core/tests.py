from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from oauth2_provider.models import AccessToken, Application

from core.content_policy import civil_text_contains_military_terms
from core.models import AuditLogEntry, Contribution, Profile, Request


User = get_user_model()


class ContentPolicyTests(TestCase):
    def test_civil_military_keyword_detection(self):
        self.assertTrue(civil_text_contains_military_terms("AK-47", "test"))
        self.assertTrue(civil_text_contains_military_terms("Need ammo 7.62", "x"))
        self.assertFalse(civil_text_contains_military_terms("Need food", "rice and water"))


class RequestModelValidationTests(TestCase):
    def test_civil_request_is_blocked_if_contains_military_terms(self):
        r = Request(
            title="АК47 для президента",
            description="x",
            category="civil",
            total_quantity=1,
            remaining_quantity=1,
            delivery_country=Request.COUNTRY_OTHER,
            delivery_kind=Request.DELIVERY_KIND_MANUAL,
            delivery_location="Somewhere",
        )
        with self.assertRaises(ValidationError):
            r.full_clean()


class AuditLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass12345")

    def test_login_writes_audit_log_entry(self):
        c = Client()
        resp = c.post("/en/login/", {"username": "u1", "password": "pass12345"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AuditLogEntry.objects.filter(action="auth.login", target_user=self.user).exists())


class VerificationGatingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u2", password="pass12345")
        self.profile = self.user.profile
        self.profile.verification_status = Profile.VERIFICATION_PENDING
        self.profile.is_verified = False
        self.profile.save(update_fields=["verification_status", "is_verified"])

    def test_unverified_user_is_blocked_from_create_request_post(self):
        c = Client()
        self.assertTrue(c.login(username="u2", password="pass12345"))

        resp = c.post(
            "/en/create/",
            {
                "title": "Need water",
                "description": "bottles",
                "category": "civil",
                "total_quantity": 1,
            },
        )
        # Blocked by verification gate (redirect)
        self.assertEqual(resp.status_code, 302)


class ContributionFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass12345")
        op = self.owner.profile
        op.verification_status = Profile.VERIFICATION_VERIFIED
        op.is_verified = True
        op.preferred_dropoff_kind = Request.DELIVERY_KIND_MANUAL
        op.preferred_dropoff_point = "NP Kyiv"
        op.save(
            update_fields=[
                "verification_status",
                "is_verified",
                "preferred_dropoff_kind",
                "preferred_dropoff_point",
            ]
        )

        self.contrib = User.objects.create_user(username="contrib", password="pass12345")
        cp = self.contrib.profile
        cp.verification_status = Profile.VERIFICATION_VERIFIED
        cp.is_verified = True
        cp.save(update_fields=["verification_status", "is_verified"])

        self.req = Request.objects.create(
            title="Need food",
            description="rice",
            category="civil",
            total_quantity=10,
            remaining_quantity=10,
            created_by=self.owner,
            delivery_country=Request.COUNTRY_UA,
            delivery_kind=Request.DELIVERY_KIND_MANUAL,
            delivery_location="manual",
        )

    def test_owner_accepts_proposal_sets_pending_and_reserves_quantity(self):
        c = Contribution(
            user=self.contrib,
            request=self.req,
            quantity=3,
            contrib_delivery_kind=Request.DELIVERY_KIND_NOVA,
            contrib_np_city_ref="mock-np-city-kyiv",
            contrib_np_warehouse_ref="mock-np-wh-1",
            contrib_np_label="Kyiv • Nova Poshta #1",
        )
        c.full_clean()
        c.save()
        self.assertEqual(c.status, Contribution.STATUS_PROPOSED)

        client = Client()
        self.assertTrue(client.login(username="owner", password="pass12345"))
        resp = client.post(f"/en/contributions/{c.id}/owner-action/", {"action": "accept", "note": "ok"})
        self.assertEqual(resp.status_code, 302)

        c.refresh_from_db()
        self.req.refresh_from_db()
        self.assertEqual(c.status, Contribution.STATUS_PENDING)
        self.assertIsNotNone(c.expires_at)
        self.assertEqual(self.req.remaining_quantity, 7)


class OAuth2ApiIntegrationTests(TestCase):
    @override_settings(ROOT_URLCONF="diploma_project.urls_coordination")
    def test_oauth2_access_token_can_access_api_requests(self):
        user = User.objects.create_user(username="apiuser", password="pass12345")
        p = user.profile
        p.verification_status = Profile.VERIFICATION_VERIFIED
        p.is_verified = True
        p.save(update_fields=["verification_status", "is_verified"])

        app = Application.objects.create(
            name="test",
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            user=user,
            redirect_uris="http://localhost/oauth/callback",
        )
        token = AccessToken.objects.create(
            user=user,
            application=app,
            token="testaccesstoken",
            expires=timezone.now() + timedelta(minutes=10),
            scope="read",
        )

        Request.objects.create(
            title="Need blankets",
            description="x",
            category="civil",
            total_quantity=1,
            remaining_quantity=1,
            created_by=user,
            delivery_country=Request.COUNTRY_UA,
            delivery_kind=Request.DELIVERY_KIND_MANUAL,
            delivery_location="manual",
        )

        c = Client(HTTP_AUTHORIZATION=f"Bearer {token.token}")
        resp = c.get("/api/requests/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Need blankets", resp.content.decode("utf-8"))

from django.test import TestCase

# Create your tests here.
