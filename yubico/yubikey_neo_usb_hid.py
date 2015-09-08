"""
module for accessing a USB HID YubiKey NEO
"""

# Copyright (c) 2012 Yubico AB
# See the file COPYING for licence statement.

__all__ = [
    # constants
    'uri_identifiers',
    # functions
    # classes
    'YubiKeyNEO_USBHID',
    'YubiKeyNEO_USBHIDError'
]

import struct

from .yubico_version import __version__
from . import yubikey_usb_hid
from . import yubikey_frame
from . import yubico_exception
from . import yubico_util

# commands from ykdef.h
_SLOT_NDEF		    = 0x08  # Write YubiKey NEO NDEF
_ACC_CODE_SIZE		= 6     # Size of access code to re-program device
_NDEF_DATA_SIZE		= 54
_SLOT_DEVICE_CONFIG = 0x11  # Write YubiKey >= 3 device config
_MODE_OTP           = 0x00
_MODE_CCID          = 0x01
_MODE_OTP_CCID      = 0x02
_MODE_U2F           = 0x03
_MODE_OTP_U2F       = 0x04
_MODE_U2F_CCID      = 0x05
_MODE_OTP_U2F_CCID  = 0x06

# from nfcdef.h
_NDEF_URI_TYPE		= ord('U')
_NDEF_TEXT_TYPE		= ord('T')

# From nfcforum-ts-rtd-uri-1.0.pdf
uri_identifiers = [
    (0x01, "http://www.",),
    (0x02, "https://www.",),
    (0x03, "http://",),
    (0x04, "https://",),
    (0x05, "tel:",),
    (0x06, "mailto:",),
    (0x07, "ftp://anonymous:anonymous@",),
    (0x08, "ftp://ftp.",),
    (0x09, "ftps://",),
    (0x0a, "sftp://",),
    (0x0b, "smb://",),
    (0x0c, "nfs://",),
    (0x0d, "ftp://",),
    (0x0e, "dav://",),
    (0x0f, "news:",),
    (0x10, "telnet://",),
    (0x11, "imap:",),
    (0x12, "rtsp://",),
    (0x13, "urn:",),
    (0x14, "pop:",),
    (0x15, "sip:",),
    (0x16, "sips:",),
    (0x17, "tftp:",),
    (0x18, "btspp://",),
    (0x19, "btl2cap://",),
    (0x1a, "btgoep://",),
    (0x1b, "tcpobex://",),
    (0x1c, "irdaobex://",),
    (0x1d, "file://",),
    (0x1e, "urn:epc:id:",),
    (0x1f, "urn:epc:tag:",),
    (0x20, "urn:epc:pat:",),
    (0x21, "urn:epc:raw:",),
    (0x22, "urn:epc:",),
    (0x23, "urn:nfc:",),
    ]

class YubiKeyNEO_USBHIDError(yubico_exception.YubicoError):
    """ Exception raised for errors with the NEO USB HID communication. """

class YubiKeyNEO_USBHIDCapabilities(yubikey_usb_hid.YubiKeyUSBHIDCapabilities):
    """
    Capabilities of current YubiKey NEO.
    """

    def have_challenge_response(self, mode):
        return self.version >= (3, 0, 0)

    def have_configuration_slot(self, slot):
        if self.version < (3, 0, 0):
            return (slot == 1)
        return slot in [1, 2]

    def have_nfc_ndef(self):
        return True

    def have_device_config(self):
        return self.version >= (3, 0, 0)


class YubiKeyNEO_USBHID(yubikey_usb_hid.YubiKeyUSBHID):
    """
    Class for accessing a YubiKey NEO over USB HID.

    The NEO is very similar to the original YubiKey (YubiKeyUSBHID)
    but does add the NDEF "slot".

    The NDEF is the tag the YubiKey emmits over it's NFC interface.
    """

    model = 'YubiKey NEO'
    description = 'YubiKey NEO'
    _capabilities_cls = YubiKeyNEO_USBHIDCapabilities

    def __init__(self, debug=False, skip=0, hid_device=None):
        """
        Find and connect to a YubiKey NEO (USB HID).

        Attributes :
            skip  -- number of YubiKeys to skip
            debug -- True or False
        """
        yubikey_usb_hid.YubiKeyUSBHID.__init__(self, debug, skip, hid_device)
        if self.version_num() >= (2, 1, 4,) and \
                self.version_num() <= (2, 1, 9,):
            self.description = 'YubiKey NEO BETA'

    def write_ndef(self, ndef):
        """


        Write an NDEF tag configuration to the YubiKey NEO.
        """
        return self._write_config(ndef, _SLOT_NDEF)

    def init_device_config(self, **kwargs):
        return YubiKeyNEO_DEVICE_CONFIG(**kwargs)

    def write_device_config(self, device_config):
        """
        Write a DEVICE_CONFIG to the YubiKey NEO.
        """
        if not self.capabilities.have_device_config():
            raise yubikey_base.YubiKeyVersionError("Device config unsupported in YubiKey NEO %s" % self.version())
        return self._write_config(device_config, _SLOT_DEVICE_CONFIG)


class YubiKeyNEO_NDEF():
    """
    Class allowing programming of a YubiKey NEO NDEF.
    """

    ndef_type = _NDEF_URI_TYPE
    ndef_str = None
    access_code = yubico_util.chr_byte(0x0) * _ACC_CODE_SIZE
    # For _NDEF_URI_TYPE
    ndef_uri_rt = 0x0  # No prepending
    # For _NDEF_TEXT_TYPE
    ndef_text_lang = b'en'
    ndef_text_enc = 'UTF-8'

    def __init__(self, data, access_code = None):
        self.ndef_str = data
        if access_code is not None:
            self.access_code = access_code

    def text(self, encoding = 'UTF-8', language = 'en'):
        """
        Configure parameters for NDEF type TEXT.

        @param encoding: The encoding used. Should be either 'UTF-8' or 'UTF16'.
        @param language: ISO/IANA language code (see RFC 3066).
        """
        self.ndef_type = _NDEF_TEXT_TYPE
        self.ndef_text_lang = language
        self.ndef_text_enc = encoding
        return self

    def type(self, url = False, text = False, other = None):
        """
        Change the NDEF type.
        """
        if (url, text, other) == (True, False, None):
            self.ndef_type = _NDEF_URI_TYPE
        elif (url, text, other) == (False, True, None):
            self.ndef_type = _NDEF_TEXT_TYPE
        elif (url, text, type(other)) == (False, False, int):
            self.ndef_type = other
        else:
            raise YubiKeyNEO_USBHIDError("Bad or conflicting NDEF type specified")
        return self

    def to_string(self):
        """
        Return the current NDEF as a string (always 64 bytes).
        """
        data = self.ndef_str
        if self.ndef_type == _NDEF_URI_TYPE:
            data = self._encode_ndef_uri_type(data)
        elif self.ndef_type == _NDEF_TEXT_TYPE:
            data = self._encode_ndef_text_params(data)
        if len(data) > _NDEF_DATA_SIZE:
            raise YubiKeyNEO_USBHIDError("NDEF payload too long")
        # typedef struct {
        #   unsigned char len;                  // Payload length
        #   unsigned char type;                 // NDEF type specifier
        #   unsigned char data[NDEF_DATA_SIZE]; // Payload size
        #   unsigned char curAccCode[ACC_CODE_SIZE]; // Access code
        # } YKNDEF;
        #
        fmt = '< B B %ss %ss' % (_NDEF_DATA_SIZE, _ACC_CODE_SIZE)
        first = struct.pack(fmt,
                            len(data),
                            self.ndef_type,
                            data.ljust(_NDEF_DATA_SIZE, b'\0'),
                            self.access_code,
                            )
        #crc = 0xffff - yubico_util.crc16(first)
        #second = first + struct.pack('<H', crc) + self.unlock_code
        return first

    def to_frame(self, slot=_SLOT_NDEF):
        """
        Return the current configuration as a YubiKeyFrame object.
        """
        data = self.to_string()
        payload = data.ljust(64, b'\0')
        return yubikey_frame.YubiKeyFrame(command = slot, payload = payload)

    def _encode_ndef_uri_type(self, data):
        """
        Implement NDEF URI Identifier Code.

        This is a small hack to replace some well known prefixes (such as http://)
        with a one byte code. If the prefix is not known, 0x00 is used.
        """
        t = 0x0
        for (code, prefix) in uri_identifiers:
            if data[:len(prefix)].decode('latin-1').lower() == prefix:
                t = code
                data = data[len(prefix):]
                break
        data = yubico_util.chr_byte(t) + data
        return data

    def _encode_ndef_text_params(self, data):
        """
        Prepend language and enconding information to data, according to
        nfcforum-ts-rtd-text-1-0.pdf
        """
        status = len(self.ndef_text_lang)
        if self.ndef_text_enc == 'UTF16':
            status = status & 0b10000000
        return yubico_util.chr_byte(status) + self.ndef_text_lang + data


class YubiKeyNEO_DEVICE_CONFIG():
    """
    Class allowing programming of a YubiKey NEO DEVICE_CONFIG.
    """

    _mode = _MODE_OTP
    _cr_timeout = 0
    _auto_eject_time = 0


    def __init__(self, mode = _MODE_OTP):
        self._mode = mode

    def cr_timeout(self, timeout = 0):
        """
        Configure the challenge-response timeout in seconds.
        """
        self._cr_timeout = timeout
        return self

    def auto_eject_time(self, auto_eject_time = 0):
        """
        Configure the auto eject time in 10x seconds.
        """
        self._auto_eject_time = auto_eject_time
        return self

    def to_string(self):
        """
        Return the current DEVICE_CONFIG as a string (always 4 bytes).
        """
        fmt = '<BBH'
        first = struct.pack(
            fmt,
            self._mode,
            self._cr_timeout,
            self._auto_eject_time
        )

        #crc = 0xffff - yubico_util.crc16(first)
        #second = first + struct.pack('<H', crc)
        return first

    def to_frame(self, slot=_SLOT_DEVICE_CONFIG):
        """
        Return the current configuration as a YubiKeyFrame object.
        """
        data = self.to_string()
        payload = data.ljust(64, b'\0')
        return yubikey_frame.YubiKeyFrame(command = slot, payload = payload)
