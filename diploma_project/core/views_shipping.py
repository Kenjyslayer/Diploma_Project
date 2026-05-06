"""JSON proxies for Ukraine carrier APIs (keys stay on server)."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .shipping.nova_poshta import search_cities, warehouses_for_city
from .shipping.ukrposhta import postoffices_by_postcode


@login_required
def api_nova_cities(request):
    key = getattr(settings, "NOVA_POSHTA_API_KEY", "") or ""
    q = request.GET.get("q", "")
    result = search_cities(key, q)
    return JsonResponse(result)


@login_required
def api_nova_warehouses(request):
    key = getattr(settings, "NOVA_POSHTA_API_KEY", "") or ""
    city_ref = request.GET.get("city_ref", "")
    result = warehouses_for_city(key, city_ref)
    return JsonResponse(result)


@login_required
def api_ukrposhta_postoffices(request):
    postcode = request.GET.get("postcode", "")
    result = postoffices_by_postcode(postcode)
    return JsonResponse(result)


# Public (no-login) endpoints used by registration drop-off picker.
def api_public_nova_cities(request):
    key = getattr(settings, "NOVA_POSHTA_API_KEY", "") or ""
    q = request.GET.get("q", "")
    result = search_cities(key, q)
    return JsonResponse(result)


def api_public_nova_warehouses(request):
    key = getattr(settings, "NOVA_POSHTA_API_KEY", "") or ""
    city_ref = request.GET.get("city_ref", "")
    result = warehouses_for_city(key, city_ref)
    return JsonResponse(result)


def api_public_ukrposhta_postoffices(request):
    postcode = request.GET.get("postcode", "")
    result = postoffices_by_postcode(postcode)
    return JsonResponse(result)
