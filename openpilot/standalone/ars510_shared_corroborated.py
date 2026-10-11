"""ARS510 object list + ACC target through one corroboration-weighted speed model (research profile `shared_corroborated`; no gates).

Protocol (unchanged from 2.6): the 742-byte 0x80 record reassembled and CRC-checked, slot ages to track ids, idle /
init-template / invalid-lateral slots dropped, no points without a fresh ego speed.
Estimation, the same for every valid track: a one-state Kalman filter on the over-ground speed.
  prior at birth   the lead moves with ego: vRel ~ N(0, PRIOR_SIGMA^2) (population of the radar's ACC targets)
  slot speed       precision = w / (SIGMA_PER_CODE x 240|7)^2: the object list's speed has slow correlated errors that
                   no weight removes (U1 / U2 / C1 / C2), so it counts only as far as the radar's own ACC decision corroborates
                   the track (w, below); an uncorroborated track keeps the prior (it moves with ego)
  ACC target       sigma = ACC_SIGMA / sqrt(w), w = exp(-m^2 / 2), m = position mismatch in units of the two lists'
                   position uncertainty: a soft association, so the ACC reading weighs in only on the track it describes
  range            precision-weighted object / ACC distance with the same w
  process noise    LEAD_ACCEL (lead acceleration)
"""
import zlib
from math import exp, isfinite

from opendbc.car import structs
from opendbc.car.interfaces import RadarInterfaceBase

RADAR_BUS, CAR_BUS = 1, 0
SPEED_ADDR, OBJECTS_ADDR, ACC_SPEED_ADDR, ACC_POS_ADDR = 0xB4, 0x80, 0x235, 0x237
RECORD_FRAMES, RECORD_LEN, SLOT_START, SLOT_LEN, SLOTS = 106, 742, 17, 36, 20
IDLE_SLOT = bytes.fromhex("FCE00000A0F07F00FFFDF71FFFA100F807000F0008000000000000000000000000000000")
VGROUND_SCALE = 0.149 / 0.15
STALE_S = 0.5  # protocol: inputs older than this are missing

PRIOR_SIGMA = 2.2  # m/s, spread of the radar's ACC-target vRel (270k cycles)
SIGMA_PER_CODE = 0.045  # m/s per 240|7 count (SCR-432)
ACC_SIGMA = 0.027  # m/s, ACC target speed fast noise (SCR-512)
LEAD_ACCEL = 1.5  # m/s^2
RANGE_SIGMA_REL, RANGE_SIGMA_MIN, LAT_SIGMA = 0.06, 1.0, 0.5  # object vs ACC position mismatch: far range reads 2-8 % short
ACC_RANGE_SIGMA = 0.02  # m


def bits(b, start, length):
  return (int.from_bytes(b, "little") >> start) & ((1 << length) - 1)


def be_bits(b, start, length):
  return (int.from_bytes(b, "big") >> start) & ((1 << length) - 1)


class C1Radar:
  def __init__(self):
    self.chunks, self.record_t, self.last_frame_t = [], 0.0, None
    self.v_ego = None
    self.slots, self.next_tid = {}, 1
    self.acc_speed = self.acc_pos = None
    self.kf = {}

  def update(self, t, bus, addr, dat):
    if bus == CAR_BUS and addr == SPEED_ADDR and len(dat) >= 7:
      self.v_ego = (t, int.from_bytes(dat[5:7], "big") * 0.01 / 3.6)
    elif bus == RADAR_BUS and addr == ACC_SPEED_ADDR and len(dat) == 8:
      self.acc_speed = (t, (be_bits(dat, 29, 11) - 1024) * 0.125) if dat[1] & 0x0F == 5 else None
    elif bus == RADAR_BUS and addr == ACC_POS_ADDR and len(dat) == 8:
      self.acc_pos = (t, be_bits(dat, 39, 13) * 0.025, (be_bits(dat, 27, 12) - 2000) * 0.01) if be_bits(dat, 10, 1) else None
    elif bus == RADAR_BUS and addr == OBJECTS_ADDR:
      record = self.reassemble(t, dat)
      if record is not None and int.from_bytes(record[737:741], "little") == zlib.crc32(record[1:737]):
        return self.points(self.record_t, record)
    return None

  def reassemble(self, t, dat):
    if len(dat) != 8 or (self.chunks and t < self.last_frame_t):
      self.chunks = []
    if len(dat) != 8:
      return None
    if dat[0] == 0x12 and dat[1] == 0xE4:
      self.chunks, self.record_t = [bytes(dat[1:8])], t
    elif self.chunks:
      self.chunks.append(bytes(dat[1:8]))
    else:
      return None
    self.last_frame_t = t
    if len(self.chunks) != RECORD_FRAMES:
      return None
    record, self.chunks = b"".join(self.chunks), []
    return record if len(record) == RECORD_LEN else None

  def track_id(self, t, slot, age):
    prev = self.slots.get(slot)
    if prev is None or t - prev[2] > 0.3 or not (age > prev[1] or age == prev[1] == 126):
      prev = (self.next_tid, age, t)
      self.next_tid += 1
    self.slots[slot] = (prev[0], age, t)
    return prev[0]

  def fresh(self, x, t):
    return x if x is not None and abs(t - x[0]) <= STALE_S else None

  def points(self, t, record):
    ego, accv, accp = self.fresh(self.v_ego, t), self.fresh(self.acc_speed, t), self.fresh(self.acc_pos, t)
    if ego is None:
      return []
    v_ego, out, live = ego[1], [], set()
    for slot in range(SLOTS):
      s = record[SLOT_START + SLOT_LEN * slot:SLOT_START + SLOT_LEN * (slot + 1)]
      age, lat = bits(s, 24, 7), bits(s, 44, 12) - 2048
      if s == IDLE_SLOT or age < 1 or abs(lat) >= 2000 or (age == 1 and bits(s, 56, 7) == 0 and bits(s, 216, 6) == 0):
        continue
      tid = self.track_id(t, slot, age)
      d, y = (bits(s, 32, 12) - 160) / 16, lat * 0.015
      vg = (bits(s, 64, 10) - 510.5) * 0.15 * VGROUND_SCALE
      w = 0.0
      if accv is not None and accp is not None:
        m2 = ((d - accp[1]) / max(RANGE_SIGMA_MIN, RANGE_SIGMA_REL * accp[1])) ** 2 + ((y - accp[2]) / LAT_SIGMA) ** 2
        w = exp(-0.5 * m2)
      readings = [(vg, w / (SIGMA_PER_CODE * max(bits(s, 240, 7), 1)) ** 2)]
      if w > 0.0:
        readings.append((accv[1] + v_ego, w / ACC_SIGMA ** 2))
        rd, ra = max(RANGE_SIGMA_MIN, RANGE_SIGMA_REL * d) ** -2, w * ACC_RANGE_SIGMA ** -2
        d = (rd * d + ra * accp[1]) / (rd + ra)
      v = self.speed(tid, t, v_ego, readings)
      live.add(tid)
      out.append((tid, d, y, v - v_ego))
    self.kf = {k: v for k, v in self.kf.items() if k in live}
    return out

  def speed(self, tid, t, v_ego, readings):
    prev = self.kf.get(tid)
    if prev is None:
      v, p = v_ego, PRIOR_SIGMA ** 2  # birth: the prior
    else:
      v, p = prev[1], prev[2] + (LEAD_ACCEL * (t - prev[0])) ** 2
    for z, prec in readings:
      k = p * prec / (1.0 + p * prec)
      v, p = v + k * (z - v), p * (1.0 - k)
    self.kf[tid] = (t, v, p)
    return v


class RadarInterface(RadarInterfaceBase):
  def __init__(self, CP, *args, **kwargs):
    super().__init__(CP, *args, **kwargs)
    self.radar, self.last_record_t = C1Radar(), None

  def update(self, can_packets):
    self.frame += 1
    points, t = None, None
    for nanos, frames in can_packets:
      t = nanos * 1e-9
      for address, dat, src in frames:
        out = self.radar.update(t, src, address, dat)
        if out is not None:
          points, self.last_record_t = out, t
    if points is None:
      if t is None or self.frame % 5 != 0 or (self.last_record_t is not None and t - self.last_record_t <= STALE_S):
        return None
      ret = structs.RadarData()
      ret.errors.radarUnavailableTemporary = self.last_record_t is not None
      return ret
    ret, pts = structs.RadarData(), []
    for track_id, d_rel, y_rel, v_rel in points:
      pt = structs.RadarData.RadarPoint()
      pt.trackId, pt.dRel, pt.yRel, pt.vRel = track_id, d_rel, y_rel, v_rel
      pts.append(pt)
    ret.points = pts  # assigned as a list: capnp-backed structs have no append
    return ret
