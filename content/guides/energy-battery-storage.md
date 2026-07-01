---
id: energy-battery-storage
title: Store and manage your power
category: energy
summary: Size, wire, and care for a battery bank so solar or wind power is there when you need it.
difficulty: 3
estimated_time: "1-2 days"
---

# Store and manage your power

Solar and wind make power when the weather allows, not when you need it. A
battery bank bridges that gap. Treated well, batteries last for years; treated
badly, they fail fast or become dangerous — so management matters as much as
size.

> **Batteries are serious.** They store a lot of energy and can deliver huge
> currents. A short circuit can melt metal and start fires; some types give off
> explosive or toxic gas. Fuse everything, ventilate, and respect them.

## Choose a battery type

- **Lead-acid (flooded or sealed):** cheap and robust, but heavy, needs
  ventilation, and dislikes being deeply discharged. Good budget option.
- **Lithium (LiFePO4):** lighter, longer-lived, tolerates deeper discharge, but
  costs more and needs a **battery management system (BMS)** and correct
  charging.
- Whatever you use, **don't mix old and new, or different types**, in one bank.

## Size the bank

Work from your daily energy use (see *Size an energy system*):

1. Decide how many days of backup you want with no sun or wind (**autonomy**).
2. Multiply daily use by those days.
3. Divide by the fraction you can safely use — lead-acid likes staying above ~50%
   charge; lithium can go deeper — so the real bank is bigger than the bare
   number.

## Wire it safely

- Use **correctly rated cable** for the current; undersized cable overheats.
- Put a **fuse or breaker** close to the battery on the main line, and a
  **disconnect switch** you can reach fast.
- Keep connections **tight and clean** — loose joints heat up and fail.
- Match series/parallel wiring to the voltage and capacity you need, keeping cells
  balanced.

```ascii
   Series — adds voltage, same capacity:

   [+ Batt 1 -]---[+ Batt 2 -]---[+ Batt 3 -]
       +                                  -
       |__________________________________|
                to system (higher voltage)

   Parallel — adds capacity, same voltage:

    +----[+ Batt 1 -]----+
    |                     |
    +----[+ Batt 2 -]----+----> to system (higher capacity)
    |                     |
    +----[+ Batt 3 -]----+
```

*Fig. 1: series wiring stacks voltage; parallel wiring stacks capacity — don't mix the two patterns on the same bank*

## Charge and care

- Use a **charge controller** suited to your source (MPPT gets more from solar;
  wind needs one with a dump load) and to the battery chemistry.
- **Don't over-discharge** — it's the fastest way to kill batteries; many
  controllers have a low-voltage cutoff to protect them.
- **Ventilate** lead-acid banks (they vent hydrogen) and keep them off freezing
  or baking surfaces — temperature affects life and capacity.
- **Check regularly:** voltage, connections, electrolyte level (flooded
  lead-acid), and any swelling, heat, or smell.

## Get the most from it

Run big loads while the sun shines or wind blows (using power directly is more
efficient than storing it), keep the bank topped up, and replace failing cells
before they drag down the rest.
