[Documentation française](GENERIC_SOAPY_VALIDATION_FR.md)

# Generic SoapySDR receiver qualification

This procedure validates a physical receiver with SDRbridge 0.7.0. Detecting a
SoapySDR factory only proves that its software module loaded; it does not prove
that the receiver, vendor driver or complete streaming path works correctly.

Validated results are recorded in the continuously updated
[hardware validation matrix](../HARDWARE_COMPATIBILITY.md). SDRbridge does not
contain model-specific rate limits or invented controls: the application uses
the capabilities reported by the selected receiver and its SoapySDR module.

## Prepare the validation computer

1. Install the Windows driver, API, firmware and hardware images recommended by
   the receiver manufacturer.
2. Confirm that the receiver works with the vendor's own utility when one is
   available.
3. Close every other application that may have opened the receiver.
4. Install the current SDRbridge release. PothosSDR is not required to run the
   packaged application.
5. Do not copy SDRbridge's private SoapySDR DLLs into PothosSDR, SDR++, ANTRACK
   or another application. The software stacks must remain isolated.

SDRbridge does not download, replace or modify vendor drivers, firmware or
hardware images. A receiver that is not correctly configured upstream cannot
be repaired by SDRbridge.

## Run the receiver test

1. Open SDRbridge without starting acquisition, then refresh the source list.
2. Confirm that the receiver appears and record its complete source label.
3. Select it and verify that sample rates, bandwidths, IQ transports, antennas,
   AGC and gains are shown only when the SoapySDR module exposes them.
4. Start at a conservative sample rate and press **Acquisition**. Wait until the
   button becomes green and the measured rate stabilizes.
5. Observe a live spectrum or waterfall for at least 60 seconds. The measured
   rate must match the selected rate and the separated loss counters must remain
   stable.
6. Add one local UDP destination at the same rate, then repeat the observation.
7. Change frequency and exercise every visible gain or AGC control. An absent
   control is not a defect when the hardware does not advertise it.
8. Perform five Stop/Play cycles, change temporarily to Simulation, then return
   to the receiver. Acquisition must restart without remaining on “waiting for
   new blocks”.
9. Increase the source rate step by step. When several IQ transports are
   advertised, test **Auto** and each relevant explicit transport.
10. Test the intended client mix, including lower-rate filtered outputs, for at
    least five minutes.
11. Export a diagnostic ZIP and capture the **Radio** and
    **Clients & Streams** pages.

## Interpret the counters

- **Source losses** are reported before SDRbridge processing by the receiver or
  its driver.
- **Queue, DSP and profile losses** indicate that SDRbridge could not process a
  block in time.
- **UDP losses or errors** belong to a destination queue, socket or network
  path.

The test report must preserve these categories instead of combining them into
one unexplained number.

## Record the result

For each receiver, record its model and tuner, driver/API version, SoapySDR
backend, complete SDRbridge label, tested rates, effective IQ transport,
visible controls, Stop/Play result, final loss counters and diagnostic report.

Only measured configurations belong in the hardware matrix. The “maximum
tested IQ rate” is evidence from a particular receiver and computer; it is not
necessarily the receiver's absolute specification limit.
