---
id: energy-low-tech-solar
title: Set up a small low-tech solar system
category: energy
summary: Size, wire, and safely run a small 12 V solar + battery system for lighting and charging.
difficulty: 3
estimated_time: "2 days"
---

# Set up a small low-tech solar system

A modest solar panel, a charge controller, and one battery can run lights, charge
phones and radios, and keep small devices alive off-grid. Keeping it low-voltage
(12 V) and simple makes it cheap, repairable, and safe to build yourself.

> **Risk:** Batteries store a lot of energy. A short across a battery's terminals
> can melt tools and start fires; lead-acid cells vent flammable, corrosive gas.
> Always fuse close to the battery, work with insulated tools, and ventilate
> battery storage. Lithium packs need a proper BMS — never charge them unmanaged.

## Materials

- One solar panel (e.g. 50–150 W) suited to your needs
- A **charge controller** rated for the panel's current with some margin —
  panel watts ÷ 12, plus a quarter (a 120 W panel is about 10 A, so fit a
  15 A controller). PWM is fine with a small "12 V" panel (36 cells, about
  18 V on its label); a larger house-roof panel (60 or 72 cells) needs an
  MPPT controller, which also gives more yield
- A deep-cycle battery (lead-acid/AGM or LiFePO₄ with a BMS)
- An inline **fuse** and holder, plus a battery isolator
- Cable, ring terminals, and a 12 V fuse/distribution block — sizes for the
  cable and fuses are worked out below
- 12 V loads: LED lights, a USB charging socket, etc.
- Tools: wire strippers and a crimping tool, screwdrivers and an insulated
  spanner, a multimeter, insulated gloves, and safety glasses — the full
  list is in [[checklist:off-grid-power-build]]

## Sizing (rough method)

1. **List your loads** and their watts × hours per day to get watt-hours/day.
2. **Battery:** daily watt-hours × days of autonomy (2 is sensible) ÷ the
   share of the battery you can use (about 0.5 for lead-acid, 0.8 for
   LiFePO₄), then ÷ 12 V for amp-hours.
3. **Panel:** it has to replace a day's use within your worst-case sun hours:
   **panel watts ≈ daily Wh ÷ peak sun hours ÷ 0.7** (the ÷ 0.7 covers about
   30% losses in the controller, wiring and charging).

> **Spec:** Worked example — 222 Wh a day, 3 winter sun hours, lead-acid:
> battery `222 × 2 ÷ 0.5 ÷ 12 ≈ 74 Ah` (fit 100 Ah); panel
> `222 ÷ 3 ÷ 0.7 ≈ 106 W` (fit at least 120 W). The full method is in
> [[energy-sizing-solar-battery]].

```ascii
   +-------------+        +------------------+        +------------+
   |   solar     |  (2)   |     charge       |  (3)   | 12V loads  |
   |   panel     |------->|   controller     |------->| lights,    |
   +-------------+        +------------------+        | USB, etc.  |
                                   ^                   +------------+
                                   | (1)
                            +-------------+
                            |   battery   |--[FUSE]-- + terminal
                            +-------------+
```

*Fig. 1: wiring order — connect (1) battery to the controller first, then (2) the panel, then (3) the loads; the fuse sits within a few centimetres of the battery's positive terminal*

## Size the cable and fuse

Cable that is too thin gets hot, and a fuse that is too big lets it burn.
These two sizes decide whether the system is safe.

1. **Current:** amps = watts ÷ 12. A 120 W panel is about 10 A; 60 W of
   lights is 5 A.
2. **Cable:** amps ÷ 3 gives the copper cross-section in mm². Round *up* to
   the next size sold. That holds for runs up to about 3 m; go one size
   thicker for anything longer. So 10 A needs 4 mm² cable.
3. **Fuse:** about a quarter more than the current the cable normally
   carries, and never more than the cable can take:

| Cable | Largest fuse |
| --- | --- |
| 1.5 mm² | 10 A |
| 2.5 mm² | 15 A |
| 4 mm² | 25 A |
| 6 mm² | 35 A |

> **Spec:** Worked example — 5 A of lights: `5 ÷ 3 ≈ 1.7`, so use 2.5 mm²
> cable; `5 × 1.25 ≈ 6.3`, so fit the next fuse up, 7.5 A — well under the
> 15 A that cable allows.

The fuse protects the cable, so it goes at the battery end of every positive
cable. If the cable maker gives a lower rating than this table, use theirs.

## Wiring order (safety matters)

1. Mount the panel where it gets unshaded midday sun, tilted toward the equator.
2. Connect the **charge controller to the battery first**, then the panel, then
   the loads — controllers detect battery voltage on power-up.
3. Put a **fuse within a few centimetres of the battery's positive terminal.**
4. Keep runs short, and use the cable sizes worked out above to avoid
   voltage drop and heat.

## Running and maintaining it

- Don't discharge lead-acid below ~50%; deep discharges shorten its life.
- Keep terminals clean and tight; check water levels on flooded batteries.
- Keep the panel clean and unshaded — even partial shade cuts output sharply.

## Where to go next

- [[energy-sizing-solar-battery]]
- [[energy-battery-storage]]
- [[checklist:off-grid-power-build]]
