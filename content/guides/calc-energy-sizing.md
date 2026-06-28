---
id: calc-energy-sizing
title: Size an energy system
category: calculations
summary: Work out your daily energy use and size panels, turbine, and batteries to meet it.
difficulty: 3
estimated_time: "2-3 hours"
---

# Size an energy system

The most common reason an off-grid system disappoints is bad sizing — too small
and the lights go out, too big and you waste scarce resources. The maths is
simple arithmetic, and getting it right once saves a lot of grief.

> **Energy vs power.** *Power* (watts, W) is the rate of use right now; *energy*
> (watt-hours, Wh) is power used over time. Bills and batteries are about energy:
> **watts × hours = watt-hours**. Almost all sizing comes back to this.

## Step 1: Add up your daily energy use

For each device, multiply its power by the hours you use it per day, then total:

- energy per device (Wh) = **watts × hours per day**
- Example: a 10 W lamp for 5 h = 50 Wh; a 60 W fridge running ~8 h equivalent =
  480 Wh. Add them all → your **daily Wh**.

Find watts on the device label, or estimate. Be honest and slightly generous.

## Step 2: Size the generation

You need to *make* at least your daily use, allowing for losses and weak weather:

1. Take your daily Wh and **add ~20-30%** for losses (wiring, charging,
   inefficiency).
2. Divide by the **usable sun-hours** (or wind-equivalent hours) for your worst
   usable season — often only a few hours a day.
3. That gives the **watts of panel (or turbine)** you need. Round up.

Example: 1000 Wh/day × 1.3 ÷ 4 sun-hours ≈ **325 W of panel**.

## Step 3: Size the battery bank

Batteries carry you through nights and bad weather:

1. Decide **days of autonomy** (e.g. 2 days with no sun).
2. **Daily Wh × days** = energy to store.
3. Divide by the fraction you can safely use (lead-acid ~50%, lithium more), so
   the real bank is bigger than the bare figure.
4. Convert to amp-hours if needed: **Ah = Wh ÷ battery voltage**.

Example: 1000 Wh × 2 days ÷ 0.5 usable = 4000 Wh; at 12 V → ~333 Ah.

## Step 4: Sanity-check and cut

- If the system comes out huge or costly, **reduce the load first** — efficient
  lamps, fewer always-on devices, running big jobs while the sun shines. Saving
  energy is cheaper than generating it.
- Re-check seasonally; winter is usually the limiting case.

Carry these numbers into the solar, wind, and battery guides to choose real
equipment.
