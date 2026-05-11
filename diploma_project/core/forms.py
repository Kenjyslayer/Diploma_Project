from typing import Optional

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Request, Contribution, Dispute


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if isinstance(
                w,
                (forms.TextInput, forms.PasswordInput, forms.EmailInput, forms.NumberInput),
            ):
                w.attrs.setdefault("class", "form-control")


class RegisterForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    phone_number = forms.CharField(
        label="Phone number",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+380..."}),
    )
    role = forms.ChoiceField(
        label="Account type",
        choices=[("civil", "Civil"), ("military", "Military")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    preferred_dropoff_kind = forms.ChoiceField(
        label="Preferred drop-off (carrier)",
        choices=[
            (Request.DELIVERY_KIND_NOVA, "Nova Poshta (branch / parcel locker)"),
            (Request.DELIVERY_KIND_UKR, "Ukrposhta (post office)"),
        ],
        widget=forms.Select(attrs={"class": "form-select", "id": "id_pref_delivery_kind"}),
    )
    preferred_np_city_ref = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_pref_np_city_ref"}),
    )
    preferred_np_city_label = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_pref_np_city_label"}),
    )
    preferred_np_warehouse_ref = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_pref_np_warehouse_ref"}),
    )
    preferred_np_label = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_pref_np_label"}),
    )
    preferred_up_postcode = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_pref_up_postcode", "placeholder": "01001"}),
    )
    preferred_up_office_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_pref_up_office_id"}),
    )
    preferred_up_label = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "id": "id_pref_up_label"}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('password1', 'password2'):
            self.fields[name].widget.attrs.setdefault('class', 'form-control')

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.email = self.cleaned_data.get('email', '')
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
            user.save(update_fields=['email', 'first_name', 'last_name'])
            profile = getattr(user, 'profile', None)
            if profile:
                profile.role = self.cleaned_data.get('role', 'civil')
                profile.phone_number = self.cleaned_data.get('phone_number', '')
                profile.preferred_dropoff_kind = self.cleaned_data.get('preferred_dropoff_kind', '')
                profile.preferred_np_city_ref = self.cleaned_data.get('preferred_np_city_ref', '')
                profile.preferred_np_warehouse_ref = self.cleaned_data.get('preferred_np_warehouse_ref', '')
                profile.preferred_np_city_label = self.cleaned_data.get('preferred_np_city_label', '')
                profile.preferred_np_label = self.cleaned_data.get('preferred_np_label', '')
                profile.preferred_up_postcode = self.cleaned_data.get('preferred_up_postcode', '')
                profile.preferred_up_office_id = self.cleaned_data.get('preferred_up_office_id', '')
                profile.preferred_up_label = self.cleaned_data.get('preferred_up_label', '')
                # Human-readable summary (kept for later auto-fill / display)
                if profile.preferred_dropoff_kind == Request.DELIVERY_KIND_NOVA:
                    profile.preferred_dropoff_point = profile.preferred_np_label
                elif profile.preferred_dropoff_kind == Request.DELIVERY_KIND_UKR:
                    profile.preferred_dropoff_point = profile.preferred_up_label
                profile.save(
                    update_fields=[
                        'role',
                        'phone_number',
                        'preferred_dropoff_point',
                        'preferred_dropoff_kind',
                        'preferred_np_city_ref',
                        'preferred_np_warehouse_ref',
                        'preferred_np_city_label',
                        'preferred_np_label',
                        'preferred_up_postcode',
                        'preferred_up_office_id',
                        'preferred_up_label',
                    ]
                )
        return user

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('preferred_dropoff_kind')
        if kind == Request.DELIVERY_KIND_NOVA:
            cleaned['preferred_up_postcode'] = ''
            cleaned['preferred_up_office_id'] = ''
            cleaned['preferred_up_label'] = ''
            # Keep city label only for NP.
            if not (
                cleaned.get('preferred_np_city_ref')
                and cleaned.get('preferred_np_warehouse_ref')
                and cleaned.get('preferred_np_label')
            ):
                self.add_error('preferred_np_label', 'Select a Nova Poshta city and branch.')
        elif kind == Request.DELIVERY_KIND_UKR:
            cleaned['preferred_np_city_ref'] = ''
            cleaned['preferred_np_warehouse_ref'] = ''
            cleaned['preferred_np_city_label'] = ''
            cleaned['preferred_np_label'] = ''
            if not (cleaned.get('preferred_up_postcode') and cleaned.get('preferred_up_label')):
                self.add_error('preferred_up_label', 'Enter postcode and select or describe an Ukrposhta office.')
        else:
            self.add_error('preferred_dropoff_kind', 'Choose your preferred carrier.')
        return cleaned


class VerificationUploadForm(forms.Form):
    passport_scan = forms.FileField(
        label="Passport scan",
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )
    reserve_plus_pdf = forms.FileField(
        label='\"Резерв+\" PDF',
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
    )


class RequestCloseForm(forms.Form):
    reason = forms.CharField(
        label='Reason for closing',
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )


class ProfileSettingsForm(forms.Form):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    phone_number = forms.CharField(
        label="Phone number",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+380..."}),
    )
    role = forms.ChoiceField(
        label="Account type",
        choices=[("civil", "Civil"), ("military", "Military")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    profile_photo = forms.ImageField(required=False)
    profile_photo_public = forms.BooleanField(required=False, initial=True)

    preferred_dropoff_kind = forms.ChoiceField(
        label="Preferred drop-off (carrier)",
        choices=[
            (Request.DELIVERY_KIND_NOVA, "Nova Poshta (branch / parcel locker)"),
            (Request.DELIVERY_KIND_UKR, "Ukrposhta (post office)"),
        ],
        widget=forms.Select(attrs={"class": "form-select", "id": "id_pref_delivery_kind"}),
    )
    preferred_np_city_ref = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"id": "id_pref_np_city_ref"}))
    preferred_np_warehouse_ref = forms.CharField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_pref_np_warehouse_ref"})
    )
    preferred_np_city_label = forms.CharField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_pref_np_city_label"})
    )
    preferred_np_label = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"id": "id_pref_np_label"}))
    preferred_up_postcode = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_pref_up_postcode", "placeholder": "01001"}),
    )
    preferred_up_office_id = forms.CharField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_pref_up_office_id"})
    )
    preferred_up_label = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "id": "id_pref_up_label"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('preferred_dropoff_kind')
        if kind == Request.DELIVERY_KIND_NOVA:
            cleaned['preferred_up_postcode'] = ''
            cleaned['preferred_up_office_id'] = ''
            cleaned['preferred_up_label'] = ''
            if not (
                cleaned.get('preferred_np_city_ref')
                and cleaned.get('preferred_np_warehouse_ref')
                and cleaned.get('preferred_np_label')
            ):
                self.add_error('preferred_np_label', 'Select a Nova Poshta city and branch.')
        elif kind == Request.DELIVERY_KIND_UKR:
            cleaned['preferred_np_city_ref'] = ''
            cleaned['preferred_np_warehouse_ref'] = ''
            cleaned['preferred_np_city_label'] = ''
            cleaned['preferred_np_label'] = ''
            if not (cleaned.get('preferred_up_postcode') and cleaned.get('preferred_up_label')):
                self.add_error('preferred_up_label', 'Enter postcode and select or describe an Ukrposhta office.')
        else:
            self.add_error('preferred_dropoff_kind', 'Choose your preferred carrier.')
        return cleaned

    def save(self):
        u = self.user
        if not u:
            return
        u.first_name = self.cleaned_data.get('first_name', '')
        u.last_name = self.cleaned_data.get('last_name', '')
        u.email = self.cleaned_data.get('email', '')
        u.save(update_fields=['first_name', 'last_name', 'email'])
        p = getattr(u, 'profile', None)
        if not p:
            return
        old_role = p.role
        new_role = self.cleaned_data.get('role', old_role)
        p.role = new_role
        p.phone_number = self.cleaned_data.get('phone_number', '')
        p.preferred_dropoff_kind = self.cleaned_data.get('preferred_dropoff_kind', '')
        p.preferred_np_city_ref = self.cleaned_data.get('preferred_np_city_ref', '')
        p.preferred_np_warehouse_ref = self.cleaned_data.get('preferred_np_warehouse_ref', '')
        p.preferred_np_city_label = self.cleaned_data.get('preferred_np_city_label', '')
        p.preferred_np_label = self.cleaned_data.get('preferred_np_label', '')
        p.preferred_up_postcode = self.cleaned_data.get('preferred_up_postcode', '')
        p.preferred_up_office_id = self.cleaned_data.get('preferred_up_office_id', '')
        p.preferred_up_label = self.cleaned_data.get('preferred_up_label', '')
        if p.preferred_dropoff_kind == Request.DELIVERY_KIND_NOVA:
            p.preferred_dropoff_point = p.preferred_np_label
        elif p.preferred_dropoff_kind == Request.DELIVERY_KIND_UKR:
            p.preferred_dropoff_point = p.preferred_up_label

        photo = self.cleaned_data.get("profile_photo")
        if photo:
            p.profile_photo = photo
        p.profile_photo_public = bool(self.cleaned_data.get("profile_photo_public"))
        # Changing account type forces re-verification.
        if old_role != new_role:
            p.is_verified = False
            p.verification_status = p.VERIFICATION_NONE
            p.verification_note = ''
            p.passport_scan = None
            p.reserve_plus_pdf = None
        p.save()


class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = [
            'title',
            'description',
            'category',
            'total_quantity',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'total_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class RequestEditForm(RequestForm):
    def clean_total_quantity(self):
        total = self.cleaned_data.get("total_quantity")
        inst = getattr(self, "instance", None)
        fulfilled = getattr(inst, "fulfilled_quantity", 0) if inst else 0
        if total is not None and fulfilled and total < fulfilled:
            raise forms.ValidationError(
                f"Total quantity cannot be less than already fulfilled ({fulfilled})."
            )
        return total


class ContributionQuantityForm(forms.Form):
    """Plain form: avoids ModelForm mapping model field errors (e.g. 'request') onto form fields."""

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )


class ContributionProposeForm(forms.Form):
    """Create or update a proposed contribution (post office / international note; no map pin)."""

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    contrib_delivery_kind = forms.ChoiceField(
        required=False,
        choices=[
            (Request.DELIVERY_KIND_NOVA, 'Nova Poshta (branch / parcel locker)'),
            (Request.DELIVERY_KIND_UKR, 'Ukrposhta (post office)'),
        ],
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_contrib_delivery_kind'}),
    )
    contrib_np_city_ref = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_contrib_np_city_ref'}),
    )
    contrib_np_warehouse_ref = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_contrib_np_warehouse_ref'}),
    )
    contrib_np_label = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_contrib_np_label'}),
    )
    contrib_up_postcode = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_contrib_up_postcode', 'placeholder': '01001'}),
    )
    contrib_up_office_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_contrib_up_office_id'}),
    )
    contrib_up_label = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'id': 'id_contrib_up_label'}),
    )
    contrib_dropoff_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'id_contrib_dropoff_note'}),
    )

    def __init__(self, *args, resource_request: Optional[Request] = None, **kwargs):
        self.resource_request = resource_request
        super().__init__(*args, **kwargs)
        if resource_request and resource_request.delivery_country == Request.COUNTRY_UA:
            self.fields['contrib_delivery_kind'].required = True
        if resource_request and resource_request.delivery_country == Request.COUNTRY_OTHER:
            self.fields['contrib_dropoff_note'].required = True
            for name in (
                'contrib_delivery_kind',
                'contrib_np_city_ref',
                'contrib_np_warehouse_ref',
                'contrib_np_label',
                'contrib_up_postcode',
                'contrib_up_office_id',
                'contrib_up_label',
            ):
                self.fields.pop(name, None)

    def clean(self):
        cleaned = super().clean()
        req = self.resource_request
        if not req:
            return cleaned
        if req.delivery_country == Request.COUNTRY_UA:
            kind = cleaned.get('contrib_delivery_kind')
            if kind == Request.DELIVERY_KIND_NOVA:
                cleaned['contrib_up_postcode'] = ''
                cleaned['contrib_up_office_id'] = ''
                cleaned['contrib_up_label'] = ''
                if not (
                    cleaned.get('contrib_np_city_ref')
                    and cleaned.get('contrib_np_warehouse_ref')
                    and cleaned.get('contrib_np_label')
                ):
                    self.add_error('contrib_np_label', 'Select a Nova Poshta city and warehouse.')
            elif kind == Request.DELIVERY_KIND_UKR:
                cleaned['contrib_np_city_ref'] = ''
                cleaned['contrib_np_warehouse_ref'] = ''
                cleaned['contrib_np_label'] = ''
                if not (cleaned.get('contrib_up_postcode') and cleaned.get('contrib_up_label')):
                    self.add_error('contrib_up_label', 'Enter postcode and select or describe an Ukrposhta office.')
            else:
                self.add_error('contrib_delivery_kind', 'Choose how you will drop off the parcel.')
        else:
            for k in (
                'contrib_delivery_kind',
                'contrib_np_city_ref',
                'contrib_np_warehouse_ref',
                'contrib_np_label',
                'contrib_up_postcode',
                'contrib_up_office_id',
                'contrib_up_label',
            ):
                cleaned[k] = ''
            if not (cleaned.get('contrib_dropoff_note') or '').strip():
                self.add_error('contrib_dropoff_note', 'Describe your shipping / handoff plan.')
        return cleaned


class OwnerContributionNoteForm(forms.Form):
    note = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional message'}),
    )


class ProofUploadForm(forms.ModelForm):
    class Meta:
        model = Contribution
        fields = ['proof_file']
        widgets = {
            'proof_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class MessageForm(forms.Form):
    body = forms.CharField(
        label='Message',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        min_length=1,
        max_length=5000,
    )
