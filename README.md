# pyzytemp

ZyTemp devices are simple serial communication devices that can measure basic properties about the world around them.
This library provides a method for interfacing with these devices and retrieving measurements from them.

Devices powered by ZyTemp include:

* https://www.co2meter.com/

Different devices have different capabilities, but in theory ZyTemp devices can report:

* Temperature
* CO2 concentration
* Relative humidity

## Installation

```
pip install pyzytemp
```

## Examples

Streaming value from a device:

```python
import pyzytemp
device = pyzytemp.find()[0]
for measurement, value in device.stream():
    if measurement == pyzytemp.Measurement.CO2:
        print(f"Current CO2 level: {value:.0f} PPM")
```

Polling for recent values from a device:

```python
import time
import pyzytemp
device = pyzytemp.find()[0]
for _ in range(32):
    time.sleep(1)
    temp = device.get_last_temperature_c()
    if temp is not None:
        print(f"Last recorded temperature: {temp:.2f}C")
```
