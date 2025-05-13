### `README.voice_design.md`

# 🧠 Cliff Voice Pipeline — Design Vision

This document outlines the **design goals**, **voice personas**, and **speech generation strategies** for the Cliff AI assistant. It defines the stylistic and architectural direction of the voice subsystem, with inspiration from LitRPG and audiobooks.

---

## 🎯 Goals

* Deliver **emotionally compelling** and **functional** speech output
* Support both **real-time feedback** and **narrative-rich responses**
* Use **multiple voice personas** to convey context and intent
* Enable **fragment stitching and caching** to optimize runtime performance
* Eventually support **hybrid local/cloud speech synthesis**

---

## 🗣️ Voice Personas

| Persona  | Role                        | Engine               | Style                    |
| -------- | --------------------------- | -------------------- | ------------------------ |
| `cliff`  | Main narrator + assistant   | Tortoise             | Calm, rich, realistic    |
| `snap`   | Fast alerts + confirmations | ElevenLabs (future)  | Energetic, clipped       |
| `system` | UI/system status            | Tortoise or stylized | Flat, neutral, robotic   |
| `echo`   | Public mode / dock PA       | TBD                  | Projected, slightly loud |

---

## ⚙️ Current Engine Setup

* **Engine**: [Tortoise TTS](https://github.com/neonbjb/tortoise-tts) (Dockerized)
* **Voice**: `william`
* **Preset**: `fast`
* **Output dir**: `results/`

All speech is generated offline using Tortoise. This prioritizes high realism over speed for now.

---

## 🧱 Speech Construction Strategy

| Pattern                | Example                                       | Strategy                             |
| ---------------------- | --------------------------------------------- | ------------------------------------ |
| **Canned phrases**     | “System online.”                              | Pre-rendered `.wav`, reused          |
| **Variable insertion** | “Activate *power mode delta*.”                | Stitch fixed prefix + dynamic phrase |
| **Role-based tone**    | "Caution!" (snapped) vs "Caution..." (warned) | Persona routing + voice selection    |
| **LitRPG echo**        | *"Power unlocked: Gravity Lance."*            | Emphasis and pitch-shifted inserts   |

---

## 🔮 Future Directions

* Support ElevenLabs for fast personas (Snap, System)
* Scripted dialogue runner from JSON
* Runtime audio stitcher (e.g. `CliffAudio.run(script.json)`)
* Emotional tone inference (based on event type or tags)
* Optional post-processing: reverb, pitch, speed for tonal control

---
