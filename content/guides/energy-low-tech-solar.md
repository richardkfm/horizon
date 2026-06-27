---
id: energy-low-tech-solar
title: Set up a small low-tech solar system
category: energy
summary: Size, wire, and safely run a small 12 V solar + battery system for lighting and charging.
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
- A **charge controller** (PWM is fine for small systems; MPPT for more yield)
- A deep-cycle battery (lead-acid/AGM or LiFePO₄ with a BMS)
- An inline **fuse** and holder sized to your wiring, plus a battery isolator
- Correctly-sized cable, ring terminals, and a 12 V fuse/distribution block
- 12 V loads: LED lights, a USB charging socket, etc.

## Sizing (rough method)

1. **List your loads** and their watts × hours per day to get watt-hours/day.
2. **Battery:** divide daily watt-hours by 12 V for amp-hours, then roughly
   double it (so you use only ~50% of a lead-acid battery and have a reserve).
3. **Panel:** size it to replace a day's use within your worst-case sun hours;
   a panel watt rating near your daily amp-hours is a sane starting point.

## Wiring order (safety matters)

1. Mount the panel where it gets unshaded midday sun, tilted toward the equator.
2. Connect the **charge controller to the battery first**, then the panel, then
   the loads — controllers detect battery voltage on power-up.
3. Put a **fuse within a few centimetres of the battery's positive terminal.**
4. Keep runs short and cable thick enough to avoid voltage drop and heat.

## Running and maintaining it

- Don't discharge lead-acid below ~50%; deep discharges shorten its life.
- Keep terminals clean and tight; check water levels on flooded batteries.
- Keep the panel clean and unshaded — even partial shade cuts output sharply.

*(Diagrams will be added under `images/` in the guides-rendering step.)*
