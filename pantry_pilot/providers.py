from __future__ import annotations

import base64
import json
import os
import ssl
from dataclasses import dataclass
from typing import Protocol
from urllib import error, parse, request

from pantry_pilot.models import GroceryLocation, GroceryProduct, Recipe
from pantry_pilot.normalization import normalize_name
from pantry_pilot.sample_data import sample_recipes


KROGER_API_BASE_URL = "https://api.kroger.com/v1"
KROGER_TOKEN_URL = "https://api.kroger.com/v1/connect/oauth2/token"


class GroceryProvider(Protocol):
    provider_name: str

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        ...

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        ...


class LocalRecipeProvider:
    def list_recipes(self) -> tuple[Recipe, ...]:
        return sample_recipes()


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderRequestError(RuntimeError):
    pass


class MockGroceryProvider:
    provider_name = "mock"

    def __init__(self) -> None:
        self._catalog = {
            "avocado": GroceryProduct("avocado", 1.0, "item", 0.9, source=self.provider_name),
            "banana": GroceryProduct("banana", 1.0, "item", 0.35, source=self.provider_name),
            "bell pepper": GroceryProduct("bell pepper", 1.0, "item", 1.0, source=self.provider_name),
            "black beans": GroceryProduct("black beans", 1.0, "can", 1.1, source=self.provider_name),
            "bread": GroceryProduct("bread", 20.0, "slice", 2.8, source=self.provider_name),
            "broccoli": GroceryProduct("broccoli", 3.0, "cup", 2.4, source=self.provider_name),
            "canned tomatoes": GroceryProduct("canned tomatoes", 1.0, "can", 1.3, source=self.provider_name),
            "carrot": GroceryProduct("carrot", 1.0, "item", 0.25, source=self.provider_name),
            "celery": GroceryProduct("celery", 1.0, "stalk", 0.2, source=self.provider_name),
            "cheddar cheese": GroceryProduct("cheddar cheese", 2.0, "cup", 3.8, source=self.provider_name),
            "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.6, source=self.provider_name),
            "chickpeas": GroceryProduct("chickpeas", 1.0, "can", 1.1, source=self.provider_name),
            "chili powder": GroceryProduct("chili powder", 4.0, "tbsp", 2.1, source=self.provider_name),
            "cinnamon": GroceryProduct("cinnamon", 12.0, "tsp", 1.8, source=self.provider_name),
            "corn": GroceryProduct("corn", 3.0, "cup", 1.9, source=self.provider_name),
            "cucumber": GroceryProduct("cucumber", 1.0, "item", 0.9, source=self.provider_name),
            "curry powder": GroceryProduct("curry powder", 4.0, "tbsp", 2.4, source=self.provider_name),
            "eggs": GroceryProduct("eggs", 12.0, "item", 3.0, source=self.provider_name),
            "feta": GroceryProduct("feta", 1.0, "cup", 3.7, source=self.provider_name),
            "frozen berries": GroceryProduct("frozen berries", 4.0, "cup", 4.4, source=self.provider_name),
            "garlic": GroceryProduct("garlic", 8.0, "clove", 0.8, source=self.provider_name),
            "granola": GroceryProduct("granola", 3.0, "cup", 3.6, source=self.provider_name),
            "ground turkey": GroceryProduct("ground turkey", 1.0, "lb", 4.2, source=self.provider_name),
            "honey": GroceryProduct("honey", 16.0, "tbsp", 4.0, source=self.provider_name),
            "lemon": GroceryProduct("lemon", 1.0, "item", 0.75, source=self.provider_name),
            "lentils": GroceryProduct("lentils", 4.0, "cup", 2.9, source=self.provider_name),
            "lime": GroceryProduct("lime", 1.0, "item", 0.5, source=self.provider_name),
            "milk": GroceryProduct("milk", 8.0, "cup", 3.2, source=self.provider_name),
            "olive oil": GroceryProduct("olive oil", 32.0, "tbsp", 6.4, source=self.provider_name),
            "onion": GroceryProduct("onion", 1.0, "item", 0.7, source=self.provider_name),
            "parmesan": GroceryProduct("parmesan", 1.5, "cup", 4.6, source=self.provider_name),
            "pasta": GroceryProduct("pasta", 16.0, "oz", 1.8, source=self.provider_name),
            "peanut butter": GroceryProduct("peanut butter", 16.0, "tbsp", 2.4, source=self.provider_name),
            "rice": GroceryProduct("rice", 8.0, "cup", 4.0, source=self.provider_name),
            "rolled oats": GroceryProduct("rolled oats", 10.0, "cup", 3.8, source=self.provider_name),
            "salsa": GroceryProduct("salsa", 2.0, "cup", 2.5, source=self.provider_name),
            "soy sauce": GroceryProduct("soy sauce", 16.0, "tbsp", 2.1, source=self.provider_name),
            "spinach": GroceryProduct("spinach", 5.0, "cup", 2.7, source=self.provider_name),
            "tofu": GroceryProduct("tofu", 1.0, "block", 2.2, source=self.provider_name),
            "tomato": GroceryProduct("tomato", 1.0, "item", 0.8, source=self.provider_name),
            "vegetable broth": GroceryProduct("vegetable broth", 4.0, "cup", 2.0, source=self.provider_name),
            "yogurt": GroceryProduct("yogurt", 4.0, "cup", 3.5, source=self.provider_name),
            "zucchini": GroceryProduct("zucchini", 1.0, "item", 0.85, source=self.provider_name),
        }

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class KrogerStoreProvider:
    provider_name = "kroger"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        location_id: str,
        chain_filter: tuple[str, ...] = ("fry", "frys", "kroger"),
        api_scope: str = "product.compact",
        timeout_seconds: float = 8.0,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.location_id = location_id
        self.chain_filter = tuple(normalize_name(value) for value in chain_filter)
        self.api_scope = api_scope
        self.timeout_seconds = timeout_seconds
        self.ssl_context = ssl_context
        self._token: str | None = None
        self._location_cache: dict[str, tuple[GroceryLocation, ...]] = {}
        self._product_cache: dict[str, GroceryProduct | None] = {}

    @classmethod
    def from_environment(
        cls,
        location_id: str,
        *,
        timeout_seconds: float = 8.0,
    ) -> "KrogerStoreProvider":
        client_id = os.getenv("KROGER_CLIENT_ID", "").strip()
        client_secret = os.getenv("KROGER_CLIENT_SECRET", "").strip()
        api_scope = os.getenv("KROGER_API_SCOPE", "product.compact").strip() or "product.compact"
        if not client_id or not client_secret:
            raise ProviderUnavailableError(
                "Kroger credentials are missing. Set KROGER_CLIENT_ID and KROGER_CLIENT_SECRET."
            )
        if not location_id.strip():
            raise ProviderUnavailableError("A Kroger or Fry's store must be selected before pricing.")
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            location_id=location_id.strip(),
            api_scope=api_scope,
            timeout_seconds=timeout_seconds,
        )

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        normalized_zip = zip_code.strip()
        if not normalized_zip:
            return ()
        if normalized_zip in self._location_cache:
            return self._location_cache[normalized_zip]

        payload = self._get_json(
            f"{KROGER_API_BASE_URL}/locations",
            {
                "filter.zipCode.near": normalized_zip,
                "filter.limit": "10",
                "filter.radiusInMiles": "20",
            },
        )
        locations: list[GroceryLocation] = []
        for row in payload.get("data", ()):
            location = self._parse_location(row)
            if location is None:
                continue
            location_text = " ".join(
                (
                    location.name,
                    location.address_line,
                    location.city,
                    location.state,
                    location.chain,
                )
            )
            normalized_text = normalize_name(location_text)
            if self.chain_filter and not any(value in normalized_text for value in self.chain_filter):
                continue
            locations.append(location)

        ordered_locations = tuple(
            sorted(locations, key=lambda item: (normalize_name(item.name), item.location_id))
        )
        self._location_cache[normalized_zip] = ordered_locations
        return ordered_locations

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        normalized_name = normalize_name(ingredient_name)
        if normalized_name in self._product_cache:
            return self._product_cache[normalized_name]

        payload = self._get_json(
            f"{KROGER_API_BASE_URL}/products",
            {
                "filter.term": normalized_name,
                "filter.locationId": self.location_id,
                "filter.limit": "10",
            },
        )

        match = self._select_best_product_match(normalized_name, payload.get("data", ()))
        self._product_cache[normalized_name] = match
        return match

    def _get_json(self, url: str, query_params: dict[str, str]) -> dict:
        access_token = self._get_access_token()
        full_url = f"{url}?{parse.urlencode(query_params)}"
        http_request = request.Request(
            full_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        try:
            with request.urlopen(
                http_request,
                timeout=self.timeout_seconds,
                context=self.ssl_context,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"Kroger API request failed ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"Kroger API request failed: {exc.reason}") from exc

    def _get_access_token(self) -> str:
        if self._token is not None:
            return self._token

        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode("ascii")
        form_body = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "scope": self.api_scope,
            }
        ).encode("utf-8")
        token_request = request.Request(
            KROGER_TOKEN_URL,
            data=form_body,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(
                token_request,
                timeout=self.timeout_seconds,
                context=self.ssl_context,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"Kroger token request failed ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"Kroger token request failed: {exc.reason}") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise ProviderRequestError("Kroger token response did not include an access token.")
        self._token = access_token
        return access_token

    def _parse_location(self, row: dict) -> GroceryLocation | None:
        location_id = str(row.get("locationId", "")).strip()
        if not location_id:
            return None
        address = row.get("address") or {}
        chain = row.get("chain") or row.get("chainName") or ""
        return GroceryLocation(
            location_id=location_id,
            name=str(row.get("name", location_id)).strip() or location_id,
            address_line=str(address.get("addressLine1", "")).strip(),
            city=str(address.get("city", "")).strip(),
            state=str(address.get("state", "")).strip(),
            postal_code=str(address.get("zipCode", "")).strip(),
            chain=str(chain).strip(),
        )

    def _select_best_product_match(self, ingredient_name: str, rows: tuple[dict, ...] | list[dict]) -> GroceryProduct | None:
        best_choice: tuple[tuple[int, str], GroceryProduct] | None = None
        for row in rows:
            description = normalize_name(str(row.get("description", "")))
            if ingredient_name not in description and description not in ingredient_name:
                continue
            candidate = self._build_product(row)
            if candidate is None:
                continue
            quality_penalty = 0 if candidate.package_price is not None else 1
            sort_key = (quality_penalty, description)
            if best_choice is None or sort_key < best_choice[0]:
                best_choice = (sort_key, candidate)
        return None if best_choice is None else best_choice[1]

    def _build_product(self, row: dict) -> GroceryProduct | None:
        description = normalize_name(str(row.get("description", "")))
        items = row.get("items") or ()
        if not description or not items:
            return None
        first_item = items[0]
        size = str(first_item.get("size", "")).strip()
        quantity, unit = _parse_size_to_quantity_and_unit(size)
        price = _extract_price(first_item.get("price") or {})
        return GroceryProduct(
            name=description,
            package_quantity=quantity,
            unit=unit,
            package_price=price,
            source=self.provider_name,
        )


@dataclass(frozen=True)
class PricingContext:
    provider: GroceryProvider
    pricing_source: str
    selected_store: str = ""
    note: str = ""
    locations: tuple[GroceryLocation, ...] = ()


class FallbackGroceryProvider:
    def __init__(self, primary: GroceryProvider, fallback: GroceryProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.provider_name = primary.provider_name
        self._primary_failed = False

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        if self._primary_failed:
            return ()
        return self.primary.lookup_locations(zip_code)

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        normalized_name = normalize_name(ingredient_name)
        if not self._primary_failed:
            try:
                product = self.primary.get_product(normalized_name)
            except ProviderRequestError:
                self._primary_failed = True
            else:
                if product is not None and product.package_price is not None:
                    return product
        fallback_product = self.fallback.get_product(normalized_name)
        if fallback_product is None:
            return None
        return GroceryProduct(
            name=fallback_product.name,
            package_quantity=fallback_product.package_quantity,
            unit=fallback_product.unit,
            package_price=fallback_product.package_price,
            source=self.fallback.provider_name,
        )


def build_pricing_context(
    pricing_mode: str,
    zip_code: str,
    store_location_id: str,
) -> PricingContext:
    normalized_mode = normalize_name(pricing_mode) or "mock"
    mock_provider = MockGroceryProvider()
    if normalized_mode != "real store":
        return PricingContext(provider=mock_provider, pricing_source="mock")

    try:
        kroger_provider = KrogerStoreProvider.from_environment(store_location_id)
    except ProviderUnavailableError as exc:
        return PricingContext(
            provider=mock_provider,
            pricing_source="mock",
            note=f"{exc} Using mock grocery prices instead.",
        )

    locations: tuple[GroceryLocation, ...] = ()
    selected_store = ""
    if zip_code.strip():
        try:
            locations = kroger_provider.lookup_locations(zip_code)
        except ProviderRequestError as exc:
            return PricingContext(
                provider=mock_provider,
                pricing_source="mock",
                note=f"{exc} Using mock grocery prices instead.",
            )

    for location in locations:
        if location.location_id == store_location_id:
            selected_store = format_location_label(location)
            break

    provider = FallbackGroceryProvider(kroger_provider, mock_provider)
    return PricingContext(
        provider=provider,
        pricing_source="kroger",
        selected_store=selected_store,
        locations=locations,
    )


def discover_kroger_locations(zip_code: str) -> PricingContext:
    mock_provider = MockGroceryProvider()
    client_id = os.getenv("KROGER_CLIENT_ID", "").strip()
    client_secret = os.getenv("KROGER_CLIENT_SECRET", "").strip()
    api_scope = os.getenv("KROGER_API_SCOPE", "product.compact").strip() or "product.compact"
    if not client_id or not client_secret:
        return PricingContext(
            provider=mock_provider,
            pricing_source="mock",
            note="Kroger credentials are missing. Set KROGER_CLIENT_ID and KROGER_CLIENT_SECRET.",
        )
    probe_provider = KrogerStoreProvider(
        client_id=client_id,
        client_secret=client_secret,
        location_id="lookup-only",
        api_scope=api_scope,
    )

    try:
        locations = probe_provider.lookup_locations(zip_code)
    except ProviderRequestError as exc:
        return PricingContext(
            provider=mock_provider,
            pricing_source="mock",
            note=str(exc),
        )

    return PricingContext(
        provider=mock_provider,
        pricing_source="kroger",
        locations=locations,
    )


def format_location_label(location: GroceryLocation) -> str:
    pieces = [location.name]
    address = ", ".join(part for part in (location.address_line, location.city, location.state) if part)
    if address:
        pieces.append(address)
    if location.postal_code:
        pieces.append(location.postal_code)
    return " | ".join(pieces)


def _extract_price(price_row: dict) -> float | None:
    for key in ("promo", "regular"):
        value = price_row.get(key)
        if value in (None, ""):
            continue
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return None


def _parse_size_to_quantity_and_unit(size: str) -> tuple[float, str]:
    normalized_size = normalize_name(size)
    if not normalized_size:
        return 1.0, "item"

    pieces = normalized_size.split()
    if not pieces:
        return 1.0, "item"

    try:
        quantity = float(pieces[0])
    except ValueError:
        return 1.0, "item"

    unit = pieces[1] if len(pieces) > 1 else "item"
    unit_map = {
        "oz": "oz",
        "ounce": "oz",
        "ounces": "oz",
        "lb": "lb",
        "lbs": "lb",
        "pound": "lb",
        "pounds": "lb",
        "ct": "item",
        "count": "item",
        "each": "item",
        "ea": "item",
        "gal": "cup",
        "qt": "cup",
    }
    mapped_unit = unit_map.get(unit, unit)
    if unit in {"gal", "qt"}:
        multiplier = 16.0 if unit == "gal" else 4.0
        return quantity * multiplier, mapped_unit
    return quantity, mapped_unit
