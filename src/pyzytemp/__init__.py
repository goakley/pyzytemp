"""
ZyTemp devices are simple serial communication devices that can measure basic
properties about the world around them.

This module provides a method for interfacing with these devices and retrieving
measurements from them.
"""
import enum
import fcntl
import io
import secrets
from typing import Dict, Generator, List, NamedTuple, Optional, Tuple, Union

import hid
import usb.core
import usb.util
from usb.util import CTRL_OUT, CTRL_RECIPIENT_INTERFACE, CTRL_TYPE_CLASS

VENDOR_ID = 0x04D9
PRODUCT_ID = 0xA052

B_REQUEST_SET_REPORT = 0x9
HID_REQUEST_SET_REPORT = 0xC0094806
W_VALUE_REPORT_TYPE_OUTPUT = 0x300


def hd(d):
    return " ".join("%02X" % e for e in d)


def decrypt(key, data):
    # https://co2meters.com/Documentation/AppNotes/AN146-RAD-0401-serial-communication.pdf
    order = [2, 4, 0, 7, 1, 6, 5, 3]
    mask = [0x48, 0x74, 0x65, 0x6D, 0x70, 0x39, 0x39, 0x65]
    bytemask = [((b >> 4) | (b << 4)) & 0xFF for b in mask]

    ordered = [0 for _ in range(max(order) + 1)]
    for i, o in enumerate(order):
        ordered[o] = data[i]
    data = ordered
    data = [d ^ k for d, k in zip(data, key)]
    data = [
        ((data[i] >> 3) | (data[(i - 1 + 8) % 8] << 5)) & 0xFF
        for i in range(len(data))
    ]
    data = [(0x100 + d - b) & 0xFF for d, b in zip(data, bytemask)]
    return data


def parse(data):
    if data[4] != 0x0D or (sum(data[:3]) & 0xFF) != data[3]:
        checksum = " ".join(f"{d:X}" for d in data)
        raise ValueError(f"Bad checksum ({checksum})")
    op = data[0]
    val = data[1] << 8 | data[2]
    return (op, val)


# http://co2meters.com/Documentation/AppNotes/AN146-RAD-0401-serial-communication.pdf
class Measurement(enum.Enum):
    """A physical factor measured by a device"""

    CO2 = 0x50
    T = 0x42
    RH = 0x44


def convert(op: int, val: int) -> Optional[Tuple[Measurement, float]]:
    converters = {
        Measurement.CO2.value: lambda v: (Measurement.CO2, v),
        Measurement.T.value: lambda v: (Measurement.T, v / 16.0 - 273.15),
        Measurement.RH.value: lambda v: (Measurement.RH, v / 100.0),
    }
    converter = converters.get(op)
    return converter(val) if converter is not None else None


class Device(NamedTuple):
    """
    A ZyTemp device.

    Devices can be queried for live values or can be asked for their most
    recently observed values.
    """

    key: List[int]
    dev: Union[io.FileIO, usb.core.Device]
    mem: Dict[Measurement, float]

    def _read(self) -> Optional[Tuple[Measurement, float]]:
        data = (
            [e for e in self.dev.read(8)]
            if isinstance(self.dev, io.FileIO)
            else self.dev.read(0x81, 8, 100)
        )
        if data[4:] != [0x0D, 0x00, 0x00, 0x00]:
            data = decrypt(self.key, data)
        op, val = parse(data)
        converted = convert(op, val)
        if converted is None:
            return None
        measurement, value = converted
        self.mem[measurement] = value
        return converted

    def poll(self) -> Tuple[Measurement, float]:
        """
        Fetch the next measurement from the device.

        This operation will block until the device provides a valid
        measurement.
        """
        while True:
            result = self._read()
            if result is not None:
                return result

    def stream(self) -> Generator[Tuple[Measurement, float], None, None]:
        """
        Provide a constant stream of measurements read from the device.

        There is no guarantee as to the order or frequency of measurements
        streamed from the device.

        This function will never complete.
        """
        while True:
            yield self.poll()

    def get_last_co2_ppm(self) -> Optional[float]:
        """
        Get the most recently recorded CO2 measurement

        Measurements are in "parts per million".
        """
        return self.mem.get(Measurement.CO2)

    def get_last_temperature_c(self) -> Optional[float]:
        """
        Get the most recently recorded temperature measurement

        Measurements are in "celsius".
        """
        return self.mem.get(Measurement.T)

    def get_last_relative_humidity_percent(self) -> Optional[float]:
        """
        Get the most recently recorded relative humidity measurement.

        Measurements are in "percent humidity" [0.0 - 1.0].
        """
        return self.mem.get(Measurement.RH)


def _find_usb(detach_kernel_driver=True) -> List[Device]:
    devs = usb.core.find(
        find_all=True,
        idVendor=VENDOR_ID,
        idProduct=PRODUCT_ID,
    )
    devices = []
    for dev in devs or []:
        if dev.is_kernel_driver_active(0) and detach_kernel_driver:
            dev.detach_kernel_driver(0)
            usb.util.claim_interface(dev, 0)
        dev.set_configuration()
        key = [secrets.randbits(8) for _ in range(8)]
        report = bytes([0x00] + key)
        # https://stackoverflow.com/questions/37943825/send-hid-report-with-pyusb
        dev.ctrl_transfer(
            CTRL_OUT | CTRL_TYPE_CLASS | CTRL_RECIPIENT_INTERFACE,
            B_REQUEST_SET_REPORT,
            W_VALUE_REPORT_TYPE_OUTPUT,
            0,
            report,
        )
        devices.append(Device(key=key, dev=dev, mem={}))
    return devices


def _find_hid() -> List[Device]:
    key = [secrets.randbits(8) for _ in range(8)]
    report = bytes([0x00] + key)
    devs = list(hid.enumerate(vid=VENDOR_ID, pid=PRODUCT_ID))
    devices = []
    for dev in devs:
        handle = open(dev["path"], "a+b", 0)
        # https://hackaday.io/project/5301/logs
        fcntl.ioctl(handle, HID_REQUEST_SET_REPORT, report)
        devices.append(Device(key=key, dev=handle, mem={}))
    return devices


def find() -> List[Device]:
    """
    Identify all attached ZyTemp devices.

    The order of devices in the resulting list is arbitrary.
    """
    return _find_hid() or _find_usb(True)
