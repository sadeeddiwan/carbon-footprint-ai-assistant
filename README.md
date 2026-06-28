# 🌍 Carbon Footprint AI Assistant

> **An Agentic AI pipeline that analyzes transportation behaviour, calculates CO₂ emissions, reasons over weekly trends, and automatically delivers personalized sustainability briefings using a local Large Language Model.**

Developed as part of the **Erasmus BIP – Agentic AI Solutions for Sustainable Innovation** at **Hochschule Heilbronn**.

---

## 🚀 Overview

The Carbon Footprint AI Assistant demonstrates how Agentic AI can automate sustainability reporting from end to end.

Instead of simply calculating emissions, the system:

* Calculates trip-level CO₂ emissions using official DEFRA 2023 emission factors.
* Aggregates weekly transportation behaviour for each user.
* Detects significant emission changes.
* Dynamically selects a recommendation strategy (Standard or Critical).
* Uses a local LLM (Mistral via Ollama) to generate personalized sustainability recommendations.
* Automatically delivers weekly reports through Matrix/Element.

---

## 🏗️ System Architecture

```text
Transportation Dataset
        │
        ▼
Emissions Calculator
        │
        ▼
Weekly Aggregation
        │
        ▼
Decision Engine
(Standard / Critical)
        │
        ▼
ReAct Agent
(Mistral via Ollama)
        │
        ▼
Weekly Carbon Briefing
        │
        ▼
Matrix / Element
```

---

## ⚙️ Technology Stack

| Technology           | Purpose                                               |
| -------------------- | ----------------------------------------------------- |
| **Python**           | Emissions calculation, aggregation and business logic |
| **n8n**              | Workflow orchestration and automation                 |
| **Mistral 7B**       | AI-powered recommendation generation                  |
| **Ollama**           | Local LLM runtime (offline inference)                 |
| **Matrix / Element** | Automated report delivery                             |
| **Docker**           | Self-hosted deployment                                |
| **DEFRA 2023**       | Official CO₂ emission factors                         |
| **GitHub**           | Version control and collaboration                     |

---

## 🔄 Workflow

```text
Manual Trigger
      │
      ▼
Read Transportation Dataset
      │
      ▼
Calculate CO₂ Emissions
      │
      ▼
Aggregate Weekly Trends
      │
      ▼
Switch
(Standard / Critical)
      │
      ▼
Set AI Context
      │
      ▼
ReAct Agent
      │
      ▼
Format Weekly Briefing
      │
      ▼
Matrix / Element
```

---

## 🤖 Agentic AI Pipeline

Unlike a traditional reporting workflow, the AI agent reasons over the transportation data before generating recommendations.

The ReAct agent follows a **Think → Act → Observe** loop and uses internal tools to:

* Retrieve weekly summaries
* Compare historical emission trends
* Identify the highest-emission journeys
* Generate data-grounded sustainability recommendations

The recommendation strategy automatically changes depending on the detected trend:

* **⚠️ Critical:** More than **10%** increase in weekly emissions.
* **🌍 Standard:** Stable, decreasing, or first-week emissions.

---

## 📊 Dataset

The synthetic transportation dataset contains:

* **293 transportation records**
* **6 commuter personas**
* **4 weeks of weekday travel**
* **6 transportation modes**

  * Car
  * Train
  * Bus
  * Subway
  * Bicycle
  * Walking

The dataset was designed to simulate realistic commuting behaviour while preserving privacy.

---

## ✨ Key Features

* End-to-end Agentic AI workflow
* Deterministic CO₂ calculations using DEFRA 2023 factors
* Weekly trend detection and routing logic
* Personalized sustainability recommendations
* Local AI inference (no external APIs)
* Automated Matrix/Element report delivery
* Docker-based deployment
* Modular Python architecture

---

## 🔮 Future Improvements

* Google Maps Timeline integration
* Private Matrix rooms for individual users
* LangGraph-based long-term agent memory
* Natural language trip logging
* Mobile application for transport tracking
* Support for additional national emission factor databases

---

## 👥 Team

**Erasmus BIP – Agentic AI Solutions for Sustainable Innovation**

* Mayuresh Parche
* Alexia Seulean
* Sadeed Shanediwan
* Roberta Aschilean
* Ranitabh Mallick
Add Ranitabh Mallick as project contributor
---

## 📄 License

Developed for academic and educational purposes as part of the Erasmus Blended Intensive Programme (BIP).

