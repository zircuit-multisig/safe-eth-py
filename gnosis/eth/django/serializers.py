import logging
from decimal import Decimal

from django.utils.translation import gettext_lazy as _

from hexbytes import HexBytes
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..constants import (
    SIGNATURE_R_MAX_VALUE,
    SIGNATURE_R_MIN_VALUE,
    SIGNATURE_S_MAX_VALUE,
    SIGNATURE_S_MIN_VALUE,
    SIGNATURE_V_MAX_VALUE,
    SIGNATURE_V_MIN_VALUE,
)
from ..utils import fast_is_checksum_address

logger = logging.getLogger(__name__)


# ================================================ #
#                Custom Fields
# ================================================ #
class EthereumAddressField(serializers.Field):
    """
    Ethereum address checksumed
    https://github.com/ethereum/EIPs/blob/master/EIPS/eip-55.md
    """

    def __init__(
        self,
        allow_zero_address: bool = False,
        allow_sentinel_address: bool = False,
        **kwargs,
    ):
        self.allow_zero_address = allow_zero_address
        self.allow_sentinel_address = allow_sentinel_address
        super().__init__(**kwargs)

    def to_representation(self, obj):
        return obj

    def to_internal_value(self, data):
        # Check if address is valid
        try:
            if not fast_is_checksum_address(data):
                raise ValueError
            elif int(data, 16) == 0 and not self.allow_zero_address:
                raise ValidationError("0x0 address is not allowed")
            elif int(data, 16) == 1 and not self.allow_sentinel_address:
                raise ValidationError("0x1 address is not allowed")
        except ValueError:
            raise ValidationError("Address %s is not checksumed" % data)

        return data


class HexadecimalField(serializers.Field):
    """
    Serializes hexadecimal values starting by `0x`. Empty values should be None or just `0x`.
    """

    default_error_messages = {
        "invalid": _("{value} is not a hexadecimal value."),
        "blank": _("This field may not be blank."),
        "max_length": _(
            "Ensure this field has no more than {max_length} hexadecimal chars (not counting 0x)."
        ),
        "min_length": _(
            "Ensure this field has at least {min_length} hexadecimal chars (not counting 0x)."
        ),
    }

    def __init__(self, **kwargs):
        self.allow_blank = kwargs.pop("allow_blank", False)
        self.max_length = kwargs.pop("max_length", None)
        self.min_length = kwargs.pop("min_length", None)
        super().__init__(**kwargs)

    def to_representation(self, obj):
        if not obj:
            return "0x"

        # We can get another types like `memoryview` from django models. `to_internal_value` is not used
        # when you provide an object instead of a json using `data`. Make sure everything is HexBytes.
        if hasattr(obj, "hex"):
            obj = HexBytes(obj.hex())
        elif not isinstance(obj, HexBytes):
            obj = HexBytes(obj)
        return obj.hex()

    def to_internal_value(self, data):
        if isinstance(data, (bytes, memoryview)):
            data = data.hex()
        elif isinstance(data, str):
            data = data.strip()  # Trim spaces
            if data.startswith("0x"):  # Remove 0x prefix
                data = data[2:]
        elif data is None:
            pass
        else:
            self.fail("invalid", value=data)

        if not data:
            if self.allow_blank:
                return None
            else:
                self.fail("blank")

        try:
            data_hex = HexBytes(data)
            data_len = len(data_hex)
            if self.min_length and data_len < self.min_length:
                self.fail("min_length", min_length=self.min_length)
            elif self.max_length and data_len > self.max_length:
                self.fail("max_length", max_length=self.max_length)
            return data_hex
        except ValueError:
            self.fail("invalid", value=data)


class Sha3HashField(HexadecimalField):
    def __init__(self, **kwargs):
        kwargs["max_length"] = 32
        kwargs["min_length"] = 32
        super().__init__(**kwargs)


class Uint96Field(serializers.DecimalField):
    def __init__(self, **kwargs):
        kwargs["min_value"] = Decimal(0)
        kwargs["max_digits"] = 29
        kwargs["decimal_places"] = 0
        super().__init__(**kwargs)


class Uint32Field(serializers.DecimalField):
    def __init__(self, **kwargs):
        kwargs["min_value"] = Decimal(0)
        kwargs["max_digits"] = 10
        kwargs["decimal_places"] = 0
        super().__init__(**kwargs)


# ================================================ #
#                Base Serializers
# ================================================ #
class SignatureSerializer(serializers.Serializer):
    v = serializers.IntegerField(
        min_value=SIGNATURE_V_MIN_VALUE, max_value=SIGNATURE_V_MAX_VALUE
    )
    r = serializers.IntegerField(
        min_value=SIGNATURE_R_MIN_VALUE, max_value=SIGNATURE_R_MAX_VALUE
    )
    s = serializers.IntegerField(
        min_value=SIGNATURE_S_MIN_VALUE, max_value=SIGNATURE_S_MAX_VALUE
    )


class TransactionSerializer(serializers.Serializer):
    from_ = EthereumAddressField()
    value = serializers.IntegerField(min_value=0)
    data = HexadecimalField()
    gas = serializers.IntegerField(min_value=0)
    gas_price = serializers.IntegerField(min_value=0)
    nonce = serializers.IntegerField(min_value=0)

    def get_fields(self):
        result = super().get_fields()
        # Rename `from_` to `from`
        from_ = result.pop("from_")
        result["from"] = from_
        return result


class TransactionResponseSerializer(serializers.Serializer):
    """
    Use chars to avoid problems with big ints (i.e. JavaScript)
    """

    from_ = EthereumAddressField()
    value = serializers.IntegerField(min_value=0)
    data = serializers.CharField()
    gas = serializers.CharField()
    gas_price = serializers.CharField()
    nonce = serializers.IntegerField(min_value=0)

    def get_fields(self):
        result = super().get_fields()
        # Rename `from_` to `from`
        from_ = result.pop("from_")
        result["from"] = from_
        return result
