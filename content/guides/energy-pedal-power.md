---
id: energy-pedal-power
title: Make power with your own muscles
category: energy
summary: Use pedal and hand-crank generators for small electrical loads like phones, radios, and lights, and use pedal power directly for grinding, pumping, and other mechanical work.
difficulty: 3
estimated_time: "A weekend to build a pedal generator"
---

# Make power with your own muscles

Human muscle is the oldest clean energy there is: no fuel, no emissions, no
weather to wait for, and good exercise besides. A pedal generator or a wind-up
radio won't run a house, but it can keep a phone charged, a radio playing,
and the lights on when the sun hasn't shone for days. And pedal power used
*directly* — to turn a grain mill or a pump — is surprisingly capable.

> **Decision:** Be realistic. A fit adult can keep up about **50–100 watts**
> on a pedal generator for an hour, after losses — roughly what one bright
> old-style light bulb used. That's plenty for small electronics and LED
> lights, and nowhere near enough for heating, cooking, or a kettle.

## What muscle power can realistically run

| Device | Typical power | An hour of pedalling (about 50–75 Wh) runs it for |
| --- | --- | --- |
| LED light | 3–5 W | 10–20 hours |
| Phone charge | 10–15 Wh per full charge | 3–5 full charges |
| Radio | 1–5 W | a day or more |
| Laptop | 30–60 W | about 1–2 hours |
| Kettle | about 2,000 W | about 2 minutes — not worth it |
| Electric heater | 1,000–2,000 W | a few minutes — not possible |

```ascii
   watts a person can keep up for an hour
   (after generator and battery losses)

   phone   |#                    ~10 W
   LEDs    |##                   ~5-20 W
   laptop  |#######              ~30-60 W
   YOU     |##########           ~50-100 W   <- the limit
   fridge  |#####                ~40 W, but 24 hours a day
   heater  |######################... 1,000+ W  (no chance)
```

*Fig. 1: what a person can supply compared to what devices draw — small
electronics and lights are a good match; anything that makes heat is not*

## Hand-crank devices

- **Wind-up radios and torches** are the simplest start: a minute of cranking
  gives several minutes of radio or light. Many also have a USB socket that
  can trickle-charge a phone in an emergency, slowly.
- **Hand-crank chargers** give about 5–20 W — tiring for more than a few
  minutes. Fine for topping up, not for daily charging.
- Choose ones with a **built-in rechargeable battery** that you can also
  charge from solar or the mains, so cranking is the backup, not the only
  way.

## Build a pedal generator

The usual design uses an ordinary bicycle on a stand, driving a small
generator, which charges a battery. You then run devices from the battery —
never straight from the generator.

```ascii
   [ bike on a stand ]
           |  rear tyre turns a roller or belt
           v
   [ generator (DC motor) ]
           |
           v
   [ blocking diode ] -> [ charge controller ]
                                 |
                                 v
                  [ fuse ] -> [ 12 V battery ]
                                 |
                                 v
                     USB charger, LED lights
```

*Fig. 2: a pedal generator chain — the battery smooths out the uneven power
from pedalling and protects your devices*

1. **A bicycle on a stand:** a turbo-trainer or a simple wooden frame that
   lifts the back wheel.
2. **A generator:** a permanent-magnet DC motor (from a scooter, treadmill,
   or similar), pressed against the tyre by a roller or driven by a belt.
3. **A blocking diode** so the battery can't push power back and spin the
   motor.
4. **A charge controller** suited to your battery, to prevent overcharging,
   plus a **fuse** close to the battery.
5. **A 12 V battery** (see [[energy-battery-storage]]), with a 12 V–USB
   adapter and 12 V LED lights.
6. **A simple meter** showing volts and watts makes pedalling more
   rewarding and shows when to ease off.

> **Tip:** If you already have a small solar system, connect the pedal
> generator to the same battery through its own controller. Then muscle
> fills the gap on dull days — see [[energy-low-tech-solar]].

## Use pedal power directly — it's more efficient

Turning muscle into electricity and back into motion wastes a lot along the
way. When the job is mechanical, connect the pedals to it directly.

- **Grain mills:** a pedal-driven mill grinds flour far faster and with less
  strain than a hand-turned one.
- **Water pumps:** a treadle pump (stepping up and down) or pedal pump lifts
  water from a well or stream to a tank or garden.
- **Workshop tools:** pedal-driven lathes, grindstones, and sharpeners.
- **Kitchen and laundry:** pedal blenders, and pedal or hand-cranked washing
  machines.

> **Pick this if:** you have a regular, heavy mechanical job like grinding
> grain or pumping water. Direct drive gets far more work out of the same
> effort than a generator does.

## Stay safe

> **Risk:** Belts, chains, rollers, and spinning wheels can trap fingers,
> hair, and loose clothing in an instant. Fit guards over every moving part,
> keep children well away while it's running, and tie back long hair.

- **Pedalling fast can push voltage high** enough to damage electronics —
  this is why devices run from the battery, not the generator.
- **Fuse the battery** and protect its terminals; a short circuit can start a
  fire.
- **Take turns,** drink water, and stop if you feel dizzy. Little and often
  beats a heroic hour.

## Where to go next

- Store what you generate: [[energy-battery-storage]].
- Look after the batteries in phones, torches, and power banks:
  [[energy-everyday-batteries]].
- Work out what you really need: [[energy-sizing-solar-battery]].
- Build a solar backbone for the rest: [[plan:off-grid-power]].
