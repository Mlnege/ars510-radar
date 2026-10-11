# 15. Recording PCS / AEB events

The radar's PCS output is decoded through an alarm-stage event
([13](13_car_bus_messages.md#a-recorded-stock-pcs-alarm-u3)). Further evidence needs isolated target identity,
warning-versus-braking stages and the radar's behavior when its car-bus output is disabled. This page specifies
what to record at a professional test facility or during an incidental event in normal driving.
For ordinary routes and other controlled tests, use [16](16_routes_and_tests.md).

Toyota cautions against testing PCS yourself
([RAV4 quick-reference guide, PCS section](https://assets.sia.toyota.com/publications/en/om-s/OM19V1QRG/pdf/OM19V1QRG.pdf)).
Do not reproduce a collision-course approach, raise speeds to reach a braking stage, or delay driver braking.
A closed lot and a homemade soft object do not establish a validated safety setup. The facility chooses
approach speeds, target design, abort conditions and vehicle control; this guide supplies the data requirements.

## 1. Isolate and identify the target

U3 had an inflatable decoration and a pickup behind it. The object list tracked the pickup and did not list the
inflatable, leaving the warning's intended target partly ambiguous
([13](13_car_bus_messages.md#a-recorded-stock-pcs-alarm-u3)). A new experiment needs separate target controls.

- Use a facility-approved, radar-characterized ADAS soft target for a radar-target experiment.
- Keep other plausible reflectors out of the target's background; record the complete scene and surveyed positions.
- Independently measure the target's position/motion and demonstrate association before interpreting a PCS edge.
- Treat a target absent from the object list as an association limit, not proof that any warning came from the camera.
  A below-threshold radar detection or unlogged camera input can remain possible.
- Do not use a person, a real parked vehicle or a homemade reflector assembly as a collision target.

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

Verify that filters or openpilot have not replaced the original car-bus outputs. CAN receipt time, video SOF and
reference acquisition time need a clock mapping; visual overlap or wall-clock notes alone do not align them.

## 3. Conditions to request from a facility

| Condition | Setup to document | Question |
|---|---|---|
| A: isolated radar-visible target | facility-approved target, radar enabled | whether the alarm and bus-1 0x100 association repeat on a uniquely identified target |
| B: target-visibility control | a separately characterized target with no competing background reflector | whether warning behavior differs with radar visibility; input source still needs independent evidence |
| C: brake-stage capture | facility-managed warning, brake-assist, pre-fill and autonomous-braking conditions, labelled separately | which car-bus commands and radar-bus values mark each stage |
| D: disabled-output condition | facility-approved control/logging setup with the radar's car-bus output disabled | whether bus-1 threat/alarm signaling remains available; no assumption that the car will warn or brake |

Keep runs that produce no warning or braking. They may be **not exercised**, not evidence that a particular bit
is invalid or that all disabled-radar decision paths are absent. The facility must distinguish driver braking,
brake assist and autonomous action; a pedal press or deceleration trace alone does not establish the actuator source.

## 4. What the result can support

Repeated, stage-labelled events can qualify an alarm or braking decision signal and its timing within the tested
configuration. They do not establish a safe AEB relay, universal target detection or restoration of stock behavior.
Short-TTC 0x195/0x196 activity without PCS action is a useful control, not a brake request.

Do not send guessed brake requests, use a warning-only signal as a brake trigger, or represent missing-message
replication as restored AEB. Fork-level relay design and safety limits require separate review
([13](13_car_bus_messages.md#where-a-relay-stands-for-developers)).

## 5. Share privately, report anonymously

Open a [research finding](https://github.com/ds-sebastian/ars510-radar/issues/new?template=research_finding.yml)
with the condition table, firmware/configuration, relative event times, observed stages, reference uncertainty
and negative results. Offer rlogs and video privately; the maintainer arranges transfer.
Keep route/dongle IDs, VINs, GPS and identifying footage out of public posts. The public repo carries anonymous
signal summaries and reproduction instructions.
