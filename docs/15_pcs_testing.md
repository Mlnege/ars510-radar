# 15. Recording PCS / AEB events

The radar's PCS output is decoded through an alarm-stage event
([13](13_car_bus_messages.md#a-recorded-stock-pcs-alarm-u3)). Further evidence needs isolated target identity,
warning-versus-braking stages and the radar's behavior when its car-bus output is disabled. This page specifies
what to record at a professional test facility or during an incidental event in normal driving.
For ordinary routes and other controlled tests, use [16](16_routes_and_tests.md).

Toyota advises leaving PCS testing to professionals
([RAV4 quick-reference guide, PCS section](https://assets.sia.toyota.com/publications/en/om-s/OM19V1QRG/pdf/OM19V1QRG.pdf)).
Keep every approach speed, target design, abort condition and vehicle-control decision with the facility's validated
procedure, and keep driver braking at its normal timing. This guide supplies the data requirements; the facility
supplies the safety setup.

## 1. Isolate and identify the target

U3 had an inflatable decoration and a pickup behind it. The object list tracked the pickup and held 0 entries for the inflatable, so either object may be the warning's intended target
([13](13_car_bus_messages.md#a-recorded-stock-pcs-alarm-u3)). A new experiment controls the target separately.

- Use a facility-approved, radar-characterized ADAS soft target for a radar-target experiment, and as the only object on
  the approach path; keep people, real parked vehicles and homemade reflector assemblies off it.
- Keep the target's background free of other plausible reflectors; record the complete scene and surveyed positions.
- Measure the target's position and motion independently and demonstrate association before interpreting a PCS edge.
- Read a gap in the object list at the target as an association limit: a radar detection below threshold or a camera input outside the log can each be the source of the warning.

## 2. Record the complete event

Keep full rlogs on all available CAN buses, synchronized external video/reference and road-camera frame indices.
Retain at least 30 seconds before and after the event, adjacent segments, driver actions and the actual sensor/
controller configuration. Record the target alias, radar/filter state, longitudinal mode and any dashboard messages.

| Group | Fields to retain |
|---|---|
| threat and alarm | bus-1 0x100, 0x195/0x196; 0x80/0x85; selected targets 0x235/0x237/0x239/0x23B; car-bus 0x33E |
| PCS and brake stages | original car-bus 0x283/0x344/0x411, brake-pressure/force fields where logged, stockFcw/stockAeb |
| driver and motion | brake/gas, carState, pose/IMU, independently logged target/ego motion, controls and planner outputs |
| configuration/health | radar firmware, fork/profile/version, CAN filter or DSU, diagnostics/restriction where available, all messages before/after |

Verify that the original car-bus outputs reach the log, whatever filter or openpilot configuration is installed. Map
CAN receipt time, video SOF and reference acquisition time to one clock with a measured offset; wall-clock notes and
visual overlap give an approximate alignment.

## 3. Conditions to request from a facility

| Condition | Setup to document | Question |
|---|---|---|
| A: isolated radar-visible target | facility-approved target, radar enabled | whether the alarm and bus-1 0x100 association repeat on a uniquely identified target |
| B: target-visibility control | a separately characterized target, the only reflector in the scene | whether warning behavior differs with radar visibility; input source needs independent evidence |
| C: brake-stage capture | facility-managed warning, brake-assist, pre-fill and autonomous-braking conditions, labelled separately | which car-bus commands and radar-bus values mark each stage |
| D: disabled-output condition | facility-approved control/logging setup with the radar's car-bus output disabled | whether bus-1 threat/alarm signaling remains available; the car's warning or braking is recorded as observed |

Keep runs where warning and braking stay idle, labelled **unexercised**: each records the conditions tried. The facility separates driver braking, brake assist and autonomous action; the
actuator source comes from the brake-pressure/force fields and stage labels, since a pedal press or deceleration trace is
common to all three.

## 4. What the result can support

Repeated, stage-labelled events qualify an alarm or braking decision signal and its timing within the tested
configuration. A safe AEB relay, universal target detection and restoration of stock behavior are separate
questions that need their own fork-level design and safety review
([13](13_car_bus_messages.md#where-a-relay-stands-for-developers)).
Short-TTC 0x195/0x196 activity with PCS idle is a useful control, with its own label.

Brake requests come from decoded, stage-labelled stock events; a warning-only signal stays a warning, and message
replication is described as replication.

## 5. Share privately, report anonymously

Open a [research finding](https://github.com/ds-sebastian/ars510-radar/issues/new?template=research_finding.yml)
with the condition table, firmware/configuration, relative event times, observed stages, reference uncertainty
and runs labelled unexercised. Offer rlogs and video privately; the maintainer arranges transfer.
Keep route/dongle IDs, VINs, GPS and identifying footage out of public posts. The public repo carries anonymous
signal summaries and reproduction instructions.
