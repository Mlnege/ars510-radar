"""ARS510 ACC target through one (range, closing speed) Kalman filter (research profile `acc_filter`).

Protocol (as `acc`): only the radar's ACC target (0x235 / 0x237) is read; target id is the track id; a lost target or a new
id restarts the filter at the measurement.
Estimation: constant-velocity model, lead acceleration as process noise; range and closing speed measured at the radar's
own resolution. One model, three constants, no conditions on the target.
"""
from opendbc.car import structs
from opendbc.car.interfaces import RadarInterfaceBase

RADAR_BUS, ACC_SPEED_ADDR, ACC_POS_ADDR = 1, 0x235, 0x237
STALE_S = 0.5
LEAD_ACCEL = 1.5  # m/s^2, process noise: lead acceleration
RANGE_SIGMA = 0.025  # m, ACC distance resolution (one count)
SPEED_SIGMA = 0.036  # m/s, 0.125 m/s quantisation / sqrt(12)


def be_bits(b: bytes, start: int, length: int) -> int:
  return (int.from_bytes(b, "big") >> start) & ((1 << length) - 1)


class RadarInterface(RadarInterfaceBase):
  def __init__(self, CP, *args, **kwargs):
    super().__init__(CP, *args, **kwargs)
    self.speed = self.pos = self.last_t = self.kf = None

  def update(self, can_packets):
    self.frame += 1
    t = None
    for nanos, frames in can_packets:
      t = nanos * 1e-9
      for address, dat, src in frames:
        if src != RADAR_BUS or address not in (ACC_SPEED_ADDR, ACC_POS_ADDR) or len(dat) != 8:
          continue
        self.last_t = t
        if address == ACC_SPEED_ADDR:
          self.speed = (be_bits(dat, 0, 5), (be_bits(dat, 29, 11) - 1024) * 0.125) if dat[1] & 0x0F == 5 else None
        else:
          self.pos = (be_bits(dat, 39, 13) * 0.025, (be_bits(dat, 27, 12) - 2000) * 0.01) if be_bits(dat, 10, 1) else None
    if t is None or self.frame % 5 != 0:
      return None
    ret = structs.RadarData()
    if self.last_t is None or t - self.last_t > STALE_S:
      ret.errors.radarUnavailableTemporary = self.last_t is not None
      self.kf = None
    elif self.speed is not None and self.pos is not None:
      tid, v = self.speed
      d, y = self.pos
      self.kf = self.filter(t, tid, d, v)
      pt = structs.RadarData.RadarPoint()
      pt.trackId, pt.dRel, pt.yRel, pt.vRel = tid, self.kf[2], y, self.kf[3]
      ret.points = [pt]
    else:
      self.kf = None
    return ret

  def filter(self, t, tid, d, v):
    if self.kf is None or self.kf[0] != tid:
      return (tid, t, d, v, RANGE_SIGMA**2, 0.0, SPEED_SIGMA**2)
    _, t0, d0, v0, pdd, pdv, pvv = self.kf
    dt = t - t0
    d0, pdd, pdv, pvv = d0 + v0 * dt, pdd + 2 * dt * pdv + dt * dt * pvv, pdv + dt * pvv, pvv + (LEAD_ACCEL * dt) ** 2
    # measurement update, range then speed (independent readings)
    k0, k1 = pdd / (pdd + RANGE_SIGMA**2), pdv / (pdd + RANGE_SIGMA**2)
    d0, v0, pdd, pdv, pvv = d0 + k0 * (d - d0), v0 + k1 * (d - d0), (1 - k0) * pdd, (1 - k0) * pdv, pvv - k1 * pdv
    k0, k1 = pdv / (pvv + SPEED_SIGMA**2), pvv / (pvv + SPEED_SIGMA**2)
    d0, v0 = d0 + k0 * (v - v0), v0 + k1 * (v - v0)
    pdd, pdv, pvv = pdd - k0 * pdv, pdv - k0 * pvv, pvv - k1 * pvv
    return (tid, t, d0, v0, pdd, pdv, pvv)
