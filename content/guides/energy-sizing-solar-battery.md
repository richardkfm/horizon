---
id: energy-sizing-solar-battery
title: How big a solar + battery system do you need?
category: energy
summary: A decision guide — work out the panel and battery size for your loads, with a worked example and sizing table.
difficulty: 2
estimated_time: "1 hour"
---

# How big a solar + battery system do you need?

The most common off-grid mistake is buying the wrong size — a panel too small to
keep up, or a battery that dies every cloudy week. You can size a system on the
back of an envelope. Start from **what you want to run**, not from the panel.

> **Decide:** Your *loads* set the battery size (how much you store) and the
> *panel* size (how fast you refill it). Work out your daily watt-hours first;
> everything else follows from that one number.

## Step 1 — Add up your daily energy use

List each device, multiply watts by hours used per day, and total the
watt-hours (Wh).

| Load | Power | Hours/day | Energy |
| --- | --- | --- | --- |
| 3 LED lights | 5 W each (15 W) | 4 h | 60 Wh |
| Phone charging | 10 W | 3 h | 30 Wh |
| Radio | 8 W | 4 h | 32 Wh |
| Laptop | 50 W | 2 h | 100 Wh |
| **Daily total** | | | **~222 Wh** |

## Step 2 — Size the battery

You want enough storage to ride through the night *and* a cloudy day, without
deep-discharging the battery (which shortens its life).

> **Spec:** Useful storage = daily Wh × **days of autonomy** ÷ **depth of
> discharge**. Use 2 days of autonomy; lead-acid tolerates ~50% discharge,
> LiFePO₄ ~80%.

Worked example (222 Wh/day, 2 days, lead-acid at 50%):
`222 × 2 ÷ 0.5 = 888 Wh`. At 12 V that is `888 ÷ 12 ≈ 74 Ah` — round up to a
**100 Ah** battery.

> **Pick this if:** you can afford it and want it to last — **LiFePO₄** gives
> far more cycles, usable depth, and weight savings. At 80% depth the same job
> needs only `222 × 2 ÷ 0.8 ÷ 12 ≈ 46 Ah`.

> **Avoid if:** budget is tight today — a cheap flooded lead-acid battery works,
> but size it bigger (50% usable) and never let it sit discharged.

## Step 3 — Size the panel

The panel has to replace a full day's use during your **worst-case sun hours**
(short winter days, cloud). Temperate winters can be as low as 2–3 useful hours.

> **Spec:** Panel watts ≈ daily Wh ÷ **peak sun hours** ÷ **0.7** (losses in the
> controller, wiring, and charging). For 222 Wh and 3 sun hours:
> `222 ÷ 3 ÷ 0.7 ≈ 106 W` — fit at least a **120 W** panel.

## Quick sizing table (lead-acid, 2 days, ~3 sun hours)

| Daily use | Battery (12 V) | Panel | Typical loads |
| --- | --- | --- | --- |
| ~100 Wh | 35 Ah | 60 W | A few lights + phone |
| ~220 Wh | 100 Ah | 120 W | Lights, phone, radio, some laptop |
| ~500 Wh | 200 Ah | 250 W | Above + fridge-free small appliances |
| ~1000 Wh | 2 × 200 Ah | 500 W | A small efficient household |

> **Risk:** Oversizing the panel without fusing and a matched charge controller
> is dangerous, not just wasteful. Always fuse close to the battery and never
> charge lithium without a BMS. The wiring details are in the solar setup guide.

## Where to go next

- Build it: follow the low-tech solar setup guide for wiring and safety.
- Cross-check your numbers with the energy-sizing calculation guide.
- Measure real use after a week and adjust — estimates are always optimistic.
