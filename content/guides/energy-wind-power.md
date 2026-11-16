---
id: energy-wind-power
title: Generate power from a small wind turbine
category: energy
summary: Site, choose, raise, and safely connect a small wind turbine to your battery system.
difficulty: 4
estimated_time: "Several days to install, after weeks of watching the wind"
---

# Generate power from a small wind turbine

Where the wind blows steadily, a small turbine complements solar well — it often
produces most in winter and at night, when panels make least. It is more
mechanically involved than solar, so plan for the moving parts and the safety.

> **Risk:** **Wind is fickle and forceful.** Power rises with the *cube* of wind speed, so a
> good site matters enormously — and a storm can destroy an unprotected turbine.
> Build in a way to slow or stop it in high wind.

## Is your site worth it?

- **Steady wind beats gusty wind.** Open coast, ridgelines, and exposed plains
  are good; sheltered valleys and built-up areas are usually poor.
- **Get above turbulence:** wind near the ground and near obstacles is broken and
  weak. A turbine wants clear air: as a rule of thumb, the
  bottom of the rotor should be at least 10 m (30 ft) above anything within
  about 150 m (500 ft). If you can't get that high, wind is probably not
  worth it on this site. Count full-grown trees and
  buildings.
- **Observe first:** watch how trees, smoke, and flags behave over weeks, or
  measure with a simple anemometer, before investing.

## Size it to your needs

Work out your daily energy use and expected wind first (see [[calc-energy-sizing|size an energy system]]). Match the turbine and battery bank to that, with margin — an oversized
tower and battery beat a turbine that never keeps up.

## What you need

- A small turbine with its matched wind charge controller and dump load
- A tilt-up guyed mast (a kit, or steel tube with a hinged base), guy wire,
  ground anchors, and turnbuckles to tension the guys
- Cable sized for the run from mast to battery, a fuse, and a disconnect
  switch
- An earth rod and clamp
- Spanners, a spirit level, a rope or hand winch for raising, and helpers

## Choose and raise it

> **Risk:** Keep the tower at least twice its full height (mast plus rotor)
> away from any overhead power line, and far enough from buildings and paths
> that it can't land on them if it falls. A mast that touches a power line
> while it is being raised can kill everyone holding it — treat every
> overhead line as live. Raise and lower the mast only in calm weather, with
> enough helpers, and keep everyone who isn't on a rope further away than
> the tower is tall.

1. **Buy a small turbine or a proven kit** rather than designing your own.
   Judge it by what it makes at your site's *usual* wind speed, not the peak
   figure on the box, and check it comes with a controller made for it. A
   home-built turbine is possible, but it needs a full set of tested plans —
   blade shape, generator, and tower — and this guide is not one.
2. **Check the storm protection.** A tail vane keeps the rotor facing the
   wind; **furling** (the rotor turns aside in high wind) or another
   automatic way to shed excess power should be built in.
3. **Tower:** the biggest, most dangerous part. Use a guyed mast that tilts
   up and down on a hinged base, so all work on the turbine happens on the
   ground. Follow the maker's guy spacing and anchor instructions.

```ascii
                 \   |   /       rotor faces the wind
                  \  |  /
                ----(*)----   <- tail vane keeps it aimed
                     |
                     |          tower (guyed mast)
            \        |        /
             \       |       /
              \      |      /     guy wires anchor the mast
               \     |     /      to solid ground
   ____________\_____|_____/____________
       anchor        |          anchor
                    anchor
```

*Fig. 1: a small wind turbine on a guyed mast — the tail vane keeps the rotor into the wind, guy wires hold the tower against storm loads*

4. **Brake:** fit a stop switch that shorts the generator's output (or a
   mechanical brake) for storms and servicing. Apply it before strong wind
   arrives, not at the height of a gale. Never just disconnect a spinning
   turbine from the battery or controller — with no load it races and can
   produce dangerous voltage. Brake it first, then isolate.

## Connect it safely

- Feed output through a **charge controller made for wind** (it must handle the
  turbine even with the battery full — a "dump load" sheds extra power so the
  turbine never free-spins to destruction).
- Wire into the **battery bank** with correctly rated cable, fusing, and a
  disconnect (see [[energy-battery-storage|store and manage your power]]).
- **Earth/ground the tower** against lightning.

## Maintain it

Inspect blades, bolts, bearings, and guy wires regularly; vibration and noise
mean trouble. Keep people clear of a spinning rotor, and always brake and secure
it before climbing or working on the tower.

## Where to go next

- [[energy-battery-storage]]
- [[calc-energy-sizing]]
- [[energy-low-tech-solar]]
