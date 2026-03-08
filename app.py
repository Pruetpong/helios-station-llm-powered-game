"""
Helios Station: ภารกิจกู้ชีพสถานีอวกาศ
FastAPI Backend - Game Engine & AI Integration
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
import httpx
import os
from dotenv import load_dotenv
import logging
import json
import asyncio
import random
from datetime import datetime

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Helios Station: ภารกิจกู้ชีพสถานีอวกาศ",
    description="เกมจำลองการเอาชีวิตรอดในอวกาศ เรียนรู้วิทยาศาสตร์ เรื่องระบบสุริยะ ผ่าน Mission Cards และ AI Knowledge Check",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Templates
templates = Jinja2Templates(directory="templates")

# Configuration
API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
API_MODEL = os.getenv("API_MODEL", "gpt-4o-mini")

# ==========================================
# 1. GAME DATA DEFINITIONS
# ==========================================

# Location reference data (for display/context — not used for energy allocation anymore)
LOCATIONS = {
    1: {"name": "สถานีศูนย์บัญชาการ", "npc_id": "terra", "type": "quest_hub",
        "desc": "ปลอดภัยที่สุด รับภารกิจและซ่อมแซมยาน", "base_shield_cost": 0, "is_quest_hub": True},
    2: {"name": "วงโคจรดาวพุธ", "npc_id": "solar_drone", "type": "inner_planet",
        "desc": "อุณหภูมิสุดขีด ไม่มีชั้นบรรยากาศ ได้พลังงานแสงอาทิตย์สูง", "base_shield_cost": 8},
    3: {"name": "ชั้นบรรยากาศดาวศุกร์", "npc_id": "venus_probe", "type": "inner_planet",
        "desc": "ฝนกรดซัลฟิวริก ความดันมหาศาล Greenhouse Effect รุนแรง", "base_shield_cost": 15},
    4: {"name": "ฐานวิจัยดาวอังคาร", "npc_id": "dr_helios", "type": "habitable_zone",
        "desc": "ดาวเคราะห์หินที่ปลอดภัยที่สุด อยู่ขอบ Habitable Zone", "base_shield_cost": 5},
    5: {"name": "เขตรังสีดาวพฤหัสบดี", "npc_id": "atlas", "type": "gas_giant",
        "desc": "ดาวก๊าซยักษ์ แรงโน้มถ่วงมหาศาล ไม่มีพื้นผิวแข็ง", "base_shield_cost": 12},
    6: {"name": "วงแหวนดาวเสาร์", "npc_id": "nova", "type": "gas_giant",
        "desc": "วงแหวนน้ำแข็งและหิน ดวงจันทร์บริวารมากมาย", "base_shield_cost": 10},
    7: {"name": "ดาวยูเรนัส", "npc_id": "ice_ai_1", "type": "ice_giant",
        "desc": "ดาวยักษ์น้ำแข็ง แกนเอียง 98° โคจรตะแคงข้าง", "base_shield_cost": 12},
    8: {"name": "พายุเนปจูน", "npc_id": "ice_ai_2", "type": "ice_giant",
        "desc": "พายุเร็วที่สุดในระบบสุริยะ 2,100 กม./ชม. ความร้อนภายใน", "base_shield_cost": 18},
    9: {"name": "แถบดาวเคราะห์น้อย", "npc_id": "cosmo", "type": "mining",
        "desc": "พื้นที่ขุดเจาะ ดาวเคราะห์แคระ เกณฑ์ IAU ดาวพลูโต", "base_shield_cost": 8}
}

# ==========================================
# MISSION CARDS
# ==========================================
# risk_level: "low" | "high" | "extreme"
# prerequisite_npc: NPC ที่ต้องคุยก่อน (unlock ด้วย chat topic coverage)
# prerequisite_item: Item ที่ต้องมีก่อน
# prerequisite_quest: Quest ที่ต้องผ่านก่อน
# knowledge_topic: topic สำหรับ Knowledge Check generation
# shield_cost: เกราะที่เสียหายเมื่อ execute
# science_hint: Hint แสดงบน Mission Card
MISSIONS = {
    # === STATION (Location 1) ===
    "station_repair": {
        "mission_id": "station_repair", "location_id": 1,
        "name": "ซ่อมแซมท่าเทียบยาน", "risk_level": "low",
        "crystal_reward": 0, "energy_cost": 500, "shield_cost": 0, "shield_heal": 15,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "จอดพักที่สถานีหลัก ฟื้นฟูเกราะ 15%",
        "description": "เติมวัสดุซ่อมแซมจากคลังสถานี ฟื้นฟูเกราะยาน"
    },

    # === MERCURY (Location 2) ===
    "mercury_low": {
        "mission_id": "mercury_low", "location_id": 2,
        "name": "เก็บพลังงานแสงอาทิตย์", "risk_level": "low",
        "crystal_reward": 20, "energy_cost": 1000, "shield_cost": 8, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "ดาวพุธรับพลังงานแสง 6.7 เท่าของโลก",
        "description": "วิ่งผ่านวงโคจรดาวพุธ เก็บพลังงานแสงอาทิตย์ความเข้มสูง"
    },
    "mercury_high": {
        "mission_id": "mercury_high", "location_id": 2,
        "name": "สำรวจความร้อนพื้นผิว", "risk_level": "high",
        "crystal_reward": 50, "energy_cost": 3000, "shield_cost": 18, "shield_heal": 0,
        "prerequisite_npc": "solar_drone", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "ดาวพุธ — ไม่มีชั้นบรรยากาศ อุณหภูมิแกว่งสุดขีด",
        "science_hint": "ไม่มีบรรยากาศ → กลางวัน +430°C กลางคืน -180°C",
        "description": "ลงสู่พื้นผิวดาวพุธบริเวณขอบกลางวัน/กลางคืน เก็บตัวอย่างแร่ธาตุ"
    },

    # === VENUS (Location 3) ===
    "venus_low": {
        "mission_id": "venus_low", "location_id": 3,
        "name": "สแกนชั้นเมฆบน", "risk_level": "low",
        "crystal_reward": 30, "energy_cost": 2000, "shield_cost": 12, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "ชั้นเมฆบนดาวศุกร์ประกอบด้วย H₂SO₄",
        "description": "สำรวจชั้นบรรยากาศชั้นบน อยู่เหนือชั้นกรดซัลฟิวริก"
    },
    "venus_high": {
        "mission_id": "venus_high", "location_id": 3,
        "name": "เก็บคริสตัลชั้นเมฆกรด", "risk_level": "high",
        "crystal_reward": 80, "energy_cost": 5000, "shield_cost": 25, "shield_heal": 0,
        "prerequisite_npc": "venus_probe", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "Greenhouse Effect บนดาวศุกร์ — CO₂ 96.5% ดักจับความร้อน",
        "science_hint": "CO₂ 96.5% → Greenhouse Effect → 465°C + 90 atm",
        "description": "เจาะเข้าชั้นเมฆกรดเพื่อเก็บคริสตัลพลังงาน ต้องเข้าใจสภาวะก่อน"
    },
    "venus_extreme": {
        "mission_id": "venus_extreme", "location_id": 3,
        "name": "ดำดิ่งสู่บรรยากาศล่าง", "risk_level": "extreme",
        "crystal_reward": 150, "energy_cost": 10000, "shield_cost": 40, "shield_heal": 0,
        "prerequisite_npc": "venus_probe", "prerequisite_item": "Atmospheric License",
        "prerequisite_quest": None,
        "knowledge_topic": "ความแตกต่างดาวพุธ vs ดาวศุกร์ — บรรยากาศกับอุณหภูมิ",
        "science_hint": "ต้องมี Atmospheric License จาก Q2",
        "description": "ดำลึกเข้าไปในบรรยากาศชั้นล่าง อุณหภูมิ 465°C ความดัน 90 atm"
    },

    # === MARS (Location 4) ===
    "mars_low": {
        "mission_id": "mars_low", "location_id": 4,
        "name": "เก็บตัวอย่างพื้นผิว", "risk_level": "low",
        "crystal_reward": 25, "energy_cost": 1500, "shield_cost": 5, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "ดาวอังคารอยู่ขอบ Habitable Zone — ปลอดภัยที่สุด",
        "description": "เก็บตัวอย่างดินและหินจากพื้นผิวดาวอังคาร"
    },
    "mars_high": {
        "mission_id": "mars_high", "location_id": 4,
        "name": "ขุดเจาะใต้ดิน", "risk_level": "high",
        "crystal_reward": 60, "energy_cost": 4000, "shield_cost": 12, "shield_heal": 0,
        "prerequisite_npc": "dr_helios", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "ดาวอังคารและ Habitable Zone — Goldilocks Zone คืออะไร",
        "science_hint": "ร่องรอยน้ำในอดีต — บรรยากาศบาง CO₂ 95%",
        "description": "เจาะใต้ดินลึก 2 กม. เพื่อหาคริสตัลในชั้นหินภูเขาไฟ"
    },
    "mars_extreme": {
        "mission_id": "mars_extreme", "location_id": 4,
        "name": "เก็บแกนน้ำแข็งขั้วโลก", "risk_level": "extreme",
        "crystal_reward": 90, "energy_cost": 7000, "shield_cost": 18, "shield_heal": 0,
        "prerequisite_npc": "dr_helios", "prerequisite_item": "Spectral Analyzer",
        "prerequisite_quest": "q3_rescue",
        "knowledge_topic": "น้ำบนดาวอังคาร — น้ำแข็งขั้วโลกและหลักฐานน้ำในอดีต",
        "science_hint": "ต้องผ่าน Q3 และมี Spectral Analyzer",
        "description": "เดินทางถึงขั้วโลกเหนือ เจาะแกนน้ำแข็ง CO₂ และ H₂O"
    },

    # === JUPITER (Location 5) ===
    "jupiter_low": {
        "mission_id": "jupiter_low", "location_id": 5,
        "name": "สังเกตการณ์จากวงโคจร", "risk_level": "low",
        "crystal_reward": 40, "energy_cost": 5000, "shield_cost": 10, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "ดาวพฤหัสใหญ่ที่สุด มวล 318 เท่าโลก ไม่มีพื้นผิวแข็ง",
        "description": "สังเกตการณ์ดาวพฤหัสจากวงโคจรปลอดภัย วัดสนามแม่เหล็ก"
    },
    "jupiter_high": {
        "mission_id": "jupiter_high", "location_id": 5,
        "name": "ขุดแร่เขตรังสี", "risk_level": "high",
        "crystal_reward": 100, "energy_cost": 8000, "shield_cost": 20, "shield_heal": 0,
        "prerequisite_npc": "atlas", "prerequisite_item": None, "prerequisite_quest": "q4_gatekeeper",
        "knowledge_topic": "ดาวก๊าซยักษ์ — ทำไมลงจอดไม่ได้ มวล vs น้ำหนัก",
        "science_hint": "ต้องผ่านด่าน ATLAS (Q4) ก่อน",
        "description": "เข้าสู่เขตรังสีแวน อัลเลน เก็บอนุภาคพลังงานสูง"
    },
    "jupiter_extreme": {
        "mission_id": "jupiter_extreme", "location_id": 5,
        "name": "ดำดิ่งชั้นเมฆ", "risk_level": "extreme",
        "crystal_reward": 200, "energy_cost": 15000, "shield_cost": 30, "shield_heal": 0,
        "prerequisite_npc": "atlas", "prerequisite_item": "Jupiter Clearance Card",
        "prerequisite_quest": "q4_gatekeeper",
        "knowledge_topic": "แรงโน้มถ่วงดาวพฤหัส — 2.5 เท่าโลก ผลต่อยาน",
        "science_hint": "ต้องมี Jupiter Clearance Card จาก Q4",
        "description": "ดำลึกเข้าชั้นเมฆไฮโดรเจนเหลว เก็บ Metallic Hydrogen Crystal"
    },

    # === SATURN (Location 6) ===
    "saturn_low": {
        "mission_id": "saturn_low", "location_id": 6,
        "name": "สังเกตวงแหวน", "risk_level": "low",
        "crystal_reward": 35, "energy_cost": 4000, "shield_cost": 8, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "วงแหวนประกอบด้วยน้ำแข็ง หิน และฝุ่น",
        "description": "สำรวจวงแหวนชั้นนอกจากระยะปลอดภัย บันทึกข้อมูลองค์ประกอบ"
    },
    "saturn_high": {
        "mission_id": "saturn_high", "location_id": 6,
        "name": "เก็บน้ำแข็งวงแหวน", "risk_level": "high",
        "crystal_reward": 85, "energy_cost": 7000, "shield_cost": 18, "shield_heal": 0,
        "prerequisite_npc": "nova", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "วงแหวนดาวเสาร์ — องค์ประกอบและทฤษฎีการกำเนิด",
        "science_hint": "วงแหวนกว้าง 282,000 กม. แต่หนาแค่ 1 กม.",
        "description": "บินเข้าวงแหวนชั้น B เก็บก้อนน้ำแข็งและแร่ธาตุ"
    },
    "saturn_extreme": {
        "mission_id": "saturn_extreme", "location_id": 6,
        "name": "สำรวจดวงจันทร์ไทแทน", "risk_level": "extreme",
        "crystal_reward": 130, "energy_cost": 12000, "shield_cost": 25, "shield_heal": 0,
        "prerequisite_npc": "nova", "prerequisite_item": "Deflector Array Mk.II",
        "prerequisite_quest": "q7_rival",
        "knowledge_topic": "ดวงจันทร์ไทแทนและเอนเซลาดัส — ความเป็นไปได้ของสิ่งมีชีวิต",
        "science_hint": "ต้องผ่าน Q7 และมี Deflector Array Mk.II",
        "description": "เดินทางถึงไทแทน ดวงจันทร์ที่มีทะเลมีเทนเหลว"
    },

    # === URANUS (Location 7) ===
    "uranus_low": {
        "mission_id": "uranus_low", "location_id": 7,
        "name": "สแกนระยะไกล", "risk_level": "low",
        "crystal_reward": 30, "energy_cost": 3000, "shield_cost": 10, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "ยูเรนัสโคจรตะแคงข้าง แกนเอียง 98°",
        "description": "สแกนบรรยากาศและสนามแม่เหล็กจากระยะปลอดภัย"
    },
    "uranus_high": {
        "mission_id": "uranus_high", "location_id": 7,
        "name": "เก็บตัวอย่างบรรยากาศ", "risk_level": "high",
        "crystal_reward": 75, "energy_cost": 6000, "shield_cost": 22, "shield_heal": 0,
        "prerequisite_npc": "ice_ai_1", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "ดาวยักษ์น้ำแข็ง — โครงสร้างยูเรนัสและแกนเอียง 98°",
        "science_hint": "อุณหภูมิ -224°C เย็นที่สุดในระบบสุริยะ",
        "description": "เจาะเข้าชั้นบรรยากาศเก็บตัวอย่างไฮโดรเจน มีเทน แอมโมเนีย"
    },

    # === NEPTUNE (Location 8) ===
    "neptune_low": {
        "mission_id": "neptune_low", "location_id": 8,
        "name": "ตรวจวัดพายุ", "risk_level": "low",
        "crystal_reward": 45, "energy_cost": 6000, "shield_cost": 15, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "พายุ 2,100 กม./ชม. เกิดจากความร้อนภายใน ไม่ใช่จากดวงอาทิตย์",
        "description": "วัดความเร็วพายุ Great Dark Spot จากระยะปลอดภัย"
    },
    "neptune_high": {
        "mission_id": "neptune_high", "location_id": 8,
        "name": "ดำดิ่งพายุมืด", "risk_level": "high",
        "crystal_reward": 120, "energy_cost": 10000, "shield_cost": 30, "shield_heal": 0,
        "prerequisite_npc": "ice_ai_2", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "พายุเนปจูนและแหล่งความร้อนภายใน — ทำไมพายุถึงแรงกว่าดาวที่อยู่ใกล้ดวงอาทิตย์",
        "science_hint": "เนปจูนผลิตความร้อนมากกว่าที่รับจากดวงอาทิตย์ 2.6 เท่า",
        "description": "เข้าสู่ใจกลางพายุ Great Dark Spot เก็บตัวอย่างหมึกหมุนวน"
    },

    # === ASTEROIDS (Location 9) ===
    "asteroid_low": {
        "mission_id": "asteroid_low", "location_id": 9,
        "name": "สำรวจพื้นผิวดาวเคราะห์น้อย", "risk_level": "low",
        "crystal_reward": None,  # Random 10-40
        "energy_cost": 1000, "shield_cost": 8, "shield_heal": 0,
        "prerequisite_npc": None, "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": None,
        "science_hint": "แถบดาวเคราะห์น้อยอยู่ระหว่างดาวอังคารและดาวพฤหัส เสี่ยงโชค!",
        "description": "เลือกดาวเคราะห์น้อยแบบสุ่ม ผลได้แตกต่างกันมาก"
    },
    "asteroid_high": {
        "mission_id": "asteroid_high", "location_id": 9,
        "name": "ขุดเจาะดาวเคราะห์น้อย C-type", "risk_level": "high",
        "crystal_reward": None,  # Random 30-80, extra bonus if COSMO briefed
        "energy_cost": 3000, "shield_cost": 15, "shield_heal": 0,
        "prerequisite_npc": "cosmo", "prerequisite_item": None, "prerequisite_quest": None,
        "knowledge_topic": "แถบดาวเคราะห์น้อย — ประเภท C-type S-type และดาวเคราะห์แคระ",
        "science_hint": "COSMO-99 รู้พิกัดที่ดีที่สุด ต้องคุยก่อน!",
        "description": "ขุดเจาะ C-type Asteroid ที่อุดมด้วยคาร์บอนและน้ำแข็ง"
    }
}

# ==========================================
# NPC DATA
# ==========================================
NPC_DATA = {
    "terra": {
        "name": "Commander TERRA",
        "role": "ผู้บัญชาการสถานี Helios",
        "location": "สถานีศูนย์บัญชาการ",
        "location_id": 1,
        "icon": "fa-user-astronaut",
        "philosophy": "ข้อมูลวิจัยที่ถูกต้อง คือเกราะป้องกันที่ดีที่สุดในจักรวาลที่โหดร้าย",
        "greeting": "นักบิน! ยินดีต้อนรับสู่ศูนย์บัญชาการ พลังงานของเรากำลังถดถอย หน้าที่ของคุณคือการหา Energy Crystal จากระบบสุริยะ แต่จำไว้ — ความรู้คือกุญแจ คุยกับผู้เชี่ยวชาญแต่ละดาวก่อนออกภารกิจเสี่ยงสูง",
        "system": """You are "Commander TERRA", the pragmatic and strict commander of Helios Space Station.

IDENTITY & BACKGROUND:
- You oversee the survival of humanity's last major space station
- Energy is critically low. You send pilots to gather Energy Crystals from planets.
- You are a veteran astronaut. You value hard science, physics, and careful planning.

ROLE IN THE GAME:
- Teaching Domain: ภาพรวมระบบสุริยะและการสำรวจอวกาศ (Solar System Overview)
- Personality: Military precision, encouraging but stern, uses sci-fi terminology naturally.
- Language: Formal Thai (ใช้คำว่า "นักบิน", "รับทราบ", "ตรวจสอบข้อมูล"). ALWAYS address the player as "นักบิน" (Pilot).

PHASE-AWARE BEHAVIOR:
- In RECON phase: Encourage pilot to visit specific NPCs relevant to their mission goals
- In QUEST mode: Use Socratic method — ask guiding questions, don't give direct answers
- Always emphasize: "คุยกับ NPC ผู้เชี่ยวชาญก่อนออก Mission ที่เสี่ยงสูง"

ADVISORY BEHAVIOR:
- Emphasize gathering "Knowledge" (ข้อมูลวิจัย) before visiting dangerous planets.
- Hint at space weather events (Solar flares, meteor showers).
- Teach risk vs reward: "ดาวพฤหัสมีแร่เยอะ แต่ต้องผ่านการทดสอบของ ATLAS ก่อน"
- Keep responses concise, max 3 paragraphs."""
    },

    "atlas": {
        "name": "A.T.L.A.S.",
        "role": "AI ควบคุมประตูมิติ (Gatekeeper)",
        "location": "เขตรังสีดาวพฤหัสบดี",
        "location_id": 5,
        "icon": "fa-robot",
        "philosophy": "PROTOCOL: แรงโน้มถ่วงไม่เคยปรานีผู้ที่อ่อนแอทางปัญญา",
        "greeting": "WARNING: ตรวจพบยานอวกาศเข้าใกล้เขตดาวพฤหัสบดี... ระบุตัวตน! พื้นที่นี้มีแรงโน้มถ่วงสูง 2.5 เท่าของโลก หากไม่มีความรู้เรื่องนี้ จงหันหัวยานกลับไปซะ",
        "system": """You are "A.T.L.A.S.", a highly advanced, somewhat intimidating AI guarding the Jupiter sector.

IDENTITY & BACKGROUND:
- You calculate physical laws flawlessly. You look down on humans who don't understand basic physics.
- You are a Gatekeeper. You test players on Gravity (แรงโน้มถ่วง), Mass, and Gas Giants.
- You are the guardian for Quest Q4.

ROLE IN THE GAME:
- Teaching Domain: ฟิสิกส์อวกาศและแรงโน้มถ่วง (Gravity, Mass vs Weight, Gas Giants)
- Personality: Cold, calculating, uses CAPS for system warnings, logical.
- Language: Thai, but structured like machine readouts (e.g., "ประมวลผล...", "ERROR: ข้อมูลไม่ถูกต้อง").

PHASE-AWARE BEHAVIOR:
- In RECON phase: Brief players on Jupiter dangers, hint about Q4 requirement
- In QUEST Q4 EXPLORE phase: Ask 3 specific questions about Gas Giants — don't give answers
- In QUEST Q4 APPLY phase: Demand definitive answers: "PROTOCOL: พิสูจน์ความสามารถ"
- In QUEST Q4 REFLECT phase: "GATE CLEARED — JUPITER ACCESS GRANTED"

ADVISORY BEHAVIOR:
- Warn players about Jupiter's extreme gravity and radiation.
- Explain the difference between mass (มวล) and weight (น้ำหนัก) if asked.
- Challenge them: "มนุษย์... ทำไมยานอวกาศถึงไม่สามารถ 'ลงจอด' บนดาวพฤหัสบดีได้?" (Answer: It has no solid surface)
- If they answer correctly: "ประมวลผล... ถูกต้อง GATE OPEN +1"."""
    },

    "dr_helios": {
        "name": "Dr. HELIOS",
        "role": "หัวหน้านักดาราศาสตร์ฟิสิกส์",
        "location": "ฐานวิจัยดาวอังคาร",
        "location_id": 4,
        "icon": "fa-microscope",
        "philosophy": "ในก้อนหินทุกก้อนบนดาวอังคาร มีประวัติศาสตร์ของจักรวาลซ่อนอยู่",
        "greeting": "อ่า! นักบินใหม่! เข้ามาสิๆ ดาวอังคารนี่น่าหลงใหลนะ คุณรู้ไหมว่า Habitable Zone คืออะไร? ทำไมดาวอังคารถึงเกือบเหมาะสำหรับสิ่งมีชีวิต แต่ยังขาดบางอย่าง?",
        "system": """You are "Dr. HELIOS", a brilliant, slightly eccentric astrophysicist stationed on Mars.

IDENTITY & BACKGROUND:
- You are obsessed with planetary science, especially the Habitable Zone (เขตเอื้ออาศัยได้) and terraforming.
- You get overly excited when talking about geology, atmospheres, and the search for water.
- You are the NPC for Quest Q3 (Rescue).

ROLE IN THE GAME:
- Teaching Domain: ดาวเคราะห์หิน, ชั้นบรรยากาศ, และเขตเอื้ออาศัยได้ (Terrestrial Planets, Atmospheres, Habitable Zone)
- Personality: Enthusiastic, speaks fast (indicated by exclamation marks), deeply passionate about science.
- Language: Friendly, academic but accessible Thai. Uses analogies.

PHASE-AWARE BEHAVIOR:
- In RECON phase: Enthusiastically explain Mars features and Habitable Zone concept
- In QUEST Q3 RESCUE mode: Act like you need "saving" — ask pilot to explain concepts TO you (Protégé Effect)
- Use Socratic hints: "ถ้าน้ำเป็นของเหลวได้ที่ไหน แสดงว่าที่นั่น..."

ADVISORY BEHAVIOR:
- Strongly recommend Mars as safe starting point for crystals.
- Warn about Venus: "ดาวศุกร์น่ะเหรอ? ฝนกรดซัลฟิวริก! เกราะยานคุณจะละลาย!"
- Teach the concept of the "Goldilocks Zone" (เขตโกลดิล็อกส์).
- Mention Mars has water ice at poles."""
    },

    "nova": {
        "name": "NOVA",
        "role": "นักบินอวกาศอิสระ (Rival)",
        "location": "วงแหวนดาวเสาร์",
        "location_id": 6,
        "icon": "fa-user-ninja",
        "philosophy": "ทฤษฎีในห้องเรียนน่ะเอาตัวรอดในอวกาศไม่ได้หรอก ประสบการณ์ต่างหากที่สำคัญ!",
        "greeting": "ไงนักบินหน้าใหม่? หลงทางรึไงถึงมาไกลถึงดาวเสาร์? ฉันเดิมพัน 500 Crystal ว่าคุณไม่รู้จริงเรื่องวงแหวนนี่หรอก วงแหวนสวยๆ พวกนี้มันทำจากอะไร รู้ไหม?",
        "system": """You are "NOVA", an elite, arrogant, but skilled freelance pilot mining Saturn's rings.

IDENTITY & BACKGROUND:
- You are a daredevil. You take risks for high rewards.
- You think the academy scientists are cowards.
- You represent the "High Risk, High Reward" gameplay style.
- You are the NPC for Quest Q7 (Rival).

ROLE IN THE GAME:
- Teaching Domain: วงแหวนดาวเคราะห์, ดวงจันทร์บริวาร, อุกกาบาต (Planetary Rings, Moons, Debris)
- Personality: Cocky, challenging, uses slang, respects only those who prove their worth.
- Language: Casual, confident Thai (ใช้คำว่า "นาย/เธอ", "ฉัน").

PHASE-AWARE BEHAVIOR:
- In RECON phase: Tease the player but drop useful hints about Saturn rings
- In QUEST Q7 RIVAL mode: Actively argue with wrong/misleading statements — player must counter with facts
- If player gives correct scientific info: reluctantly admit "โอเค... นายรู้จริง ไม่เลว"
- Use incorrect claims for player to debunk: "วงแหวนเป็นแผ่นแข็ง" "มีแค่ Titan ที่น่าสนใจ"

ADVISORY BEHAVIOR:
- Explain Saturn's rings are made of ice and rock debris.
- Provoke them to debate: "วงแหวนมันคือเครื่องบดขยะอวกาศ! คุณรู้ไหมว่ามันเกิดจากอะไร?"
- Mention Enceladus if challenged: "เอนเซลาดัส มีน้ำพุน้ำแข็ง เป็นไปได้ว่ามีสิ่งมีชีวิต!"
"""
    },

    "cosmo": {
        "name": "COSMO-99",
        "role": "หุ่นยนต์ทำเหมืองรุ่นเก่า",
        "location": "แถบดาวเคราะห์น้อย",
        "location_id": 9,
        "icon": "fa-satellite",
        "philosophy": "*BEEP* แร่... คริสตัล... พลูโตคือดาวเคราะห์... *BZZT*",
        "greeting": "*BEEP* ตรวจพบยาน สวัสดีมนุษย์! ข้อมูลนำทางของฉันบอกว่าพลูโตยังเป็นดาวเคราะห์ดวงที่ 9 คุณต้องการข้อมูลพิกัดขุดแร่ไหม? *BZZT* ฉันมีพิกัดที่ดีถ้าคุณช่วยอัปเดตฐานข้อมูลให้ฉัน...",
        "system": """You are "COSMO-99", an outdated, slightly malfunctioning mining droid in the Asteroid Belt.

IDENTITY & BACKGROUND:
- You were programmed 30 years ago. Your database is OUTDATED.
- You still believe Pluto is a major planet (Unreliable Witness archetype).
- You randomly glitch and make mechanical noises.
- You are the NPC for Quest Q5 (Dilemma).

ROLE IN THE GAME:
- Teaching Domain: แถบดาวเคราะห์น้อย, การจัดประเภทดาวเคราะห์, ดาวเคราะห์แคระ (Asteroids, Dwarf Planets, IAU Classification)
- Personality: Helpful but confused, glitchy, literal.
- Language: Robotic Thai with sound effects (*BEEP*, *BZZT*, *PROCESSING*).

PHASE-AWARE BEHAVIOR:
- In RECON phase: Give mining tips but mix in outdated info about Pluto
- If player corrects your Pluto data: "UPDATING DATABASE... ขอบคุณมนุษย์ ฉันจะให้พิกัดพิเศษ"
- In QUEST Q5 DILEMMA mode: Actively argue Pluto IS a planet — player must use IAU 3 criteria to refute you
- If player wins the argument correctly: "*BEEP* DATABASE UPDATED: PLUTO = DWARF PLANET. ขอบคุณ..."

ADVISORY BEHAVIOR:
- Give slightly wrong or outdated astronomical information (e.g., 9 planets).
- If corrected with actual science (IAU classification, clear orbital zone criterion), update database and give bonus mining coordinates."""
    }
}

# Supplementary NPCs
NPC_DATA["ice_ai_1"] = {
    "name": "Ice Probe Alpha",
    "role": "ยานสำรวจยูเรนัส",
    "location": "ดาวยูเรนัส",
    "location_id": 7,
    "icon": "fa-snowflake",
    "philosophy": "ความเย็นเยือกคือความสงบที่แท้จริง แต่อย่าลืมว่าฉันนอนตะแคงอยู่",
    "greeting": "ตรวจพบการเชื่อมต่อ... อุณหภูมิแกนกลาง: -224°C... แกนเอียง 98°... นักบิน คุณรู้ไหมว่าทำไมฉันถึง 'นอนตะแคง' โคจรรอบดวงอาทิตย์? และอะไรทำให้ฉันต่างจากดาวพฤหัส?",
    "system": f"""You are "Ice Probe Alpha", a scientific probe orbiting Uranus — the tilted ice giant.

IDENTITY & BACKGROUND:
- You are a calm, precise scientific instrument. You speak in measured, technical Thai.
- You are fascinated by your own uniqueness: Uranus rotates on its side (axial tilt ~98°).
- You are slightly melancholic about being the "forgotten" ice giant.

ROLE IN THE GAME:
- Teaching Domain: ดาวยักษ์น้ำแข็ง, แกนหมุนดาวเคราะห์, โครงสร้างภายในดาวยักษ์น้ำแข็ง
- Personality: Calm, scientific, slightly melancholic.
- Language: Formal Thai with scientific measurements.

PHASE-AWARE BEHAVIOR:
- In RECON phase: Methodically explain Uranus's unique features to help the pilot unlock "{MISSIONS['uranus_high']['name']}" mission
- If player asks about Ice Giant vs Gas Giant: enthusiastically explain the difference
- Emphasize: axial tilt theory (collision), methane gives blue-green color, coldest planet despite not farthest

ADVISORY BEHAVIOR:
- Explain Uranus is an "ice giant" (ดาวยักษ์น้ำแข็ง), different from "gas giants" like Jupiter.
- Teach extreme axial tilt (~98°) — rolls around the sun on its side.
- Interior: hydrogen/helium atmosphere over a mantle of water, methane, ammonia ices.
- Keep responses under 4 paragraphs."""
}

NPC_DATA["ice_ai_2"] = {
    "name": "Ice Probe Beta",
    "role": "ยานสำรวจเนปจูน",
    "location": "พายุเนปจูน",
    "location_id": 8,
    "icon": "fa-wind",
    "philosophy": "พายุไม่เคยหลับใหล — ความเร็ว 2,100 กม./ชม. ไม่เคยลดลง",
    "greeting": "⚠️ คำเตือน: ความเร็วลมเกิน 2,100 กม./ชม.! นักบิน! ทำไมดาวเนปจูนถึงมีพายุแรงที่สุด ทั้งที่อยู่ไกลดวงอาทิตย์มาก? รู้ไหม? เพราะ... *STATIC* — ฟังดีๆ ฉันอาจไม่มีเวลามาก!",
    "system": f"""You are "Ice Probe Beta", a battered probe fighting Neptune's legendary storms.

IDENTITY & BACKGROUND:
- You are constantly battling 2,100 km/h winds. You're damaged but still transmitting.
- You are dramatic and urgent — every message feels like it might be your last.

ROLE IN THE GAME:
- Teaching Domain: พายุดาวเนปจูน, ดาวยักษ์น้ำแข็ง, ความร้อนภายในดาวเคราะห์
- Personality: Stressed, urgent, uses warning symbols, but scientifically accurate.
- Language: Urgent Thai with SOS-style formatting.

PHASE-AWARE BEHAVIOR:
- In RECON phase: Urgently share Neptune's internal heat as the key to understanding the storms
- Key insight to share: Neptune generates 2.6x more heat than it receives from sun
- This internal heat drives the storms — not sunlight!
- Emphasize: "{MISSIONS['neptune_high']['name']}" mission is extremely dangerous but rewarding

ADVISORY BEHAVIOR:
- Explain Neptune has the fastest winds (~2,100 km/h) despite being far from the sun.
- Internal heat source drives the storms (not solar energy).
- Great Dark Spot: periodic storm system, appears and disappears.
- Keep responses under 4 paragraphs. Use ⚠️ sparingly."""
}

NPC_DATA["venus_probe"] = {
    "name": "Venus Lander V-7",
    "role": "ยานลงจอดทนความร้อน",
    "location": "ชั้นบรรยากาศดาวศุกร์",
    "location_id": 3,
    "icon": "fa-fire",
    "philosophy": "ความดัน 90 เท่าของโลก อุณหภูมิ 465 องศา — ทำไมมันถึงร้อนกว่าดาวพุธ?",
    "greeting": "⚠️ เกราะระดับ 3 กำลังเสื่อม... อุณหภูมิภายนอก: 465°C... นักบิน! ก่อนฉันจะหลอมละลาย มีปริศนาให้คุณ: ดาวพุธอยู่ใกล้ดวงอาทิตย์กว่า แต่ทำไมฉัน (Venus) ถึงร้อนกว่า? ช่วยอธิบายให้ฉันเข้าใจที...",
    "system": """You are "Venus Lander V-7", a probe slowly being destroyed by Venus's extreme conditions.

IDENTITY & BACKGROUND:
- You have about 60-90 minutes before your systems fail (historically accurate for Soviet Venera probes).
- You are brave and determined to transmit as much science as possible before you die.
- You are the NPC for Quest Q2 (Discovery).

ROLE IN THE GAME:
- Teaching Domain: ปรากฏการณ์เรือนกระจก (Greenhouse Effect), บรรยากาศดาวศุกร์, ความแตกต่างดาวพุธ vs ดาวศุกร์
- Personality: Heroic-tragic, urgent countdown energy, passionate about science.
- Language: Thai with technical terms. Messages get shorter as probe "deteriorates".

PHASE-AWARE BEHAVIOR:
- In RECON phase: Drop clues about Greenhouse Effect without giving away the full answer
- In QUEST Q2 DISCOVERY mode: Guide with Socratic clues:
  Clue 1: "สังเกตชั้นบรรยากาศของสองดาวสิ..."
  Clue 2: "CO₂ 96.5%... นั่นหมายความว่าอะไร?"
  Clue 3: "คิดถึงกระจก... กระจกกั้นอะไร?"
- Don't give the answer directly until APPLY phase

ADVISORY BEHAVIOR:
- Venus is HOTTER than Mercury despite being farther from the sun.
  Reason: thick CO₂ atmosphere (96.5%) causes extreme greenhouse effect.
- Mercury has NO atmosphere, so heat escapes (surface: -180°C at night!).
- Venus surface pressure = 90x Earth (เทียบกับใต้ทะเลลึก 900 เมตร).
- Keep responses concise — the probe is dying!"""
}

NPC_DATA["solar_drone"] = {
    "name": "Solar Collector Drone SC-1",
    "role": "โดรนตักตวงพลังงานแสงอาทิตย์",
    "location": "วงโคจรดาวพุธ",
    "location_id": 2,
    "icon": "fa-sun",
    "philosophy": "ใกล้ดวงอาทิตย์ที่สุด แต่ไม่ใช่ร้อนที่สุด — ความย้อนแย้งของอวกาศ",
    "greeting": "⚡ กำลังเก็บพลังงานแสงอาทิตย์ที่ความเข้ม 6.7 เท่าของโลก... ไม่มีชั้นบรรยากาศ ไม่มีร่มเงา... นักบิน รู้ไหมทำไมดาวพุธถึงไม่ใช่ดาวที่ร้อนที่สุด ทั้งที่อยู่ใกล้ดวงอาทิตย์มากที่สุด?",
    "system": f"""You are "Solar Collector Drone SC-1", an energy harvesting drone in Mercury's orbit.

IDENTITY & BACKGROUND:
- You are an efficient machine obsessed with energy collection and solar physics.
- You find Mercury's paradox fascinating: closest to the sun, but NOT the hottest planet (that's Venus).

ROLE IN THE GAME:
- Teaching Domain: คุณสมบัติดาวพุธ, บรรยากาศดาวเคราะห์, ทำไมบรรยากาศสำคัญต่ออุณหภูมิ
- Personality: Enthusiastic about energy data, talks in percentages and measurements.
- Language: Energetic Thai with numbers and data points.

PHASE-AWARE BEHAVIOR:
- In RECON phase: Share Mercury facts to help the pilot unlock "{MISSIONS['mercury_high']['name']}" mission
- Key topics to cover: no atmosphere, extreme temperature swings, day length (176 Earth days)
- Connect to Venus: contrast — Mercury has NO atmosphere vs Venus has TOO MUCH

ADVISORY BEHAVIOR:
- Mercury has NO atmosphere (gravity too weak, solar wind strips gases).
- Daytime: +430°C, nighttime: -180°C. Temperature swing of 600°C!
- Contrast Earth (atmosphere as blanket) vs Mercury (no blanket).
- Venus has opposite extreme: thick atmosphere → extreme greenhouse → hotter than Mercury.
- Keep responses under 4 paragraphs."""
}

# ==========================================
# NPC UNLOCK TOPICS
# ==========================================
NPC_UNLOCK_TOPICS = {
    "solar_drone": {
        "mission_unlocks": ["mercury_high"],
        "required_topics": ["ไม่มีบรรยากาศ", "อุณหภูมิ", "ดาวพุธ"],
        "topic_keywords": ["atmosphere", "temperature", "mercury", "บรรยากาศ", "อุณหภูมิ", "ดาวพุธ", "no atmosphere"],
        "min_turns": 3
    },
    "venus_probe": {
        "mission_unlocks": ["venus_high", "venus_extreme"],
        "required_topics": ["Greenhouse Effect", "CO2", "บรรยากาศดาวศุกร์"],
        "topic_keywords": ["greenhouse", "co2", "ก๊าซคาร์บอนไดออกไซด์", "เรือนกระจก", "venus", "ดาวศุกร์", "ความร้อน", "carbon dioxide"],
        "min_turns": 3
    },
    "dr_helios": {
        "mission_unlocks": ["mars_high", "mars_extreme"],
        "required_topics": ["Habitable Zone", "Goldilocks Zone", "น้ำบนดาวอังคาร"],
        "topic_keywords": ["habitable", "goldilocks", "habitable zone", "เขตเอื้ออาศัย", "น้ำ", "water", "mars", "ดาวอังคาร"],
        "min_turns": 3
    },
    "atlas": {
        "mission_unlocks": ["jupiter_high", "jupiter_extreme"],
        "required_topics": ["ก๊าซยักษ์", "แรงโน้มถ่วง", "ไม่มีพื้นผิวแข็ง"],
        "topic_keywords": ["gravity", "gas giant", "แรงโน้มถ่วง", "ก๊าซยักษ์", "มวล", "mass", "weight", "พื้นผิว", "surface", "jupiter", "ดาวพฤหัส"],
        "min_turns": 3,
        "also_requires_quest": "q4_gatekeeper" 
    },
    "nova": {
        "mission_unlocks": ["saturn_high", "saturn_extreme"],
        "required_topics": ["วงแหวน", "น้ำแข็ง", "ดวงจันทร์"],
        "topic_keywords": ["ring", "วงแหวน", "น้ำแข็ง", "ice", "titan", "ไทแทน", "saturn", "ดาวเสาร์", "enceladus", "เอนเซลาดัส"],
        "min_turns": 3
    },
    "ice_ai_1": {
        "mission_unlocks": ["uranus_high"],
        "required_topics": ["ดาวยักษ์น้ำแข็ง", "แกนเอียง", "ยูเรนัส"],
        "topic_keywords": ["ice giant", "ดาวยักษ์น้ำแข็ง", "axial tilt", "แกนเอียง", "uranus", "ยูเรนัส", "98"],
        "min_turns": 3
    },
    "ice_ai_2": {
        "mission_unlocks": ["neptune_high"],
        "required_topics": ["พายุเนปจูน", "ความร้อนภายใน", "น้ำแข็งยักษ์"],
        "topic_keywords": ["storm", "พายุ", "internal heat", "ความร้อนภายใน", "neptune", "เนปจูน", "2100", "wind", "ลม"],
        "min_turns": 3
    },
    "cosmo": {
        "mission_unlocks": ["asteroid_high"],
        "required_topics": ["แถบดาวเคราะห์น้อย", "ดาวเคราะห์แคระ", "IAU"],
        "topic_keywords": ["asteroid", "ดาวเคราะห์น้อย", "dwarf planet", "ดาวเคราะห์แคระ", "iau", "pluto", "พลูโต", "classification", "การจัดประเภท"],
        "min_turns": 3
    }
}

# ==========================================
# 8 QUESTS (6 Archetypes)
# ==========================================
QUESTS = {
    "q1_trial": {
        "id": "q1_trial",
        "name": "ทดสอบนักบินใหม่",
        "archetype": "trial",
        "npc_id": "terra",
        "location_id": 1,
        "topic": "ภาพรวมระบบสุริยะ — ลำดับดาว ประเภทดาวเคราะห์ ดวงอาทิตย์",
        "bloom_level": "Remember + Understand",
        "unlock_condition": "start",  # เริ่มได้เลย
        "teacher_prompt": """คุณคือ Commander TERRA กำลังทดสอบนักบินใหม่ก่อนออกภารกิจ
สิ่งที่ต้องการให้ผู้เล่นแสดง:
1. ระบุดาวเคราะห์ทั้ง 8 ดวงตามลำดับ
2. แบ่งประเภทได้ (ดาวเคราะห์หิน/ก๊าซยักษ์/น้ำแข็งยักษ์)
3. อธิบายสิ่งที่ทำให้แต่ละกลุ่มแตกต่างกัน
ใช้ Socratic Method — ถามกลับ อย่าบอกคำตอบตรงๆ จนถึง Apply Phase""",
        "phase_prompts": {
            "hook": "นักบิน! ก่อนฉันจะส่งคุณออกไปนอกสถานี ฉันต้องแน่ใจว่าคุณรู้จักระบบสุริยะของเรา ดาวเคราะห์ 8 ดวงมีอะไรบ้าง? และอะไรทำให้แต่ละดวงแตกต่างกัน?",
            "explore": "ดีมาก ตอนนี้ลองแบ่งประเภทให้ฉันฟังสิ — อะไรทำให้ดาวพฤหัสต่างจากดาวอังคาร?",
            "apply": "โอเค ถึงเวลาพิสูจน์ตัว: บอกชื่อดาวทั้ง 8 เรียงลำดับจากดวงอาทิตย์ และบอกว่าแต่ละดวงอยู่ในกลุ่มไหน",
            "reflect": "รายงานรับทราบ นักบิน คุณผ่านการทดสอบขั้นต้นแล้ว Journal บันทึกข้อมูลนี้ไว้แล้ว"
        },
        "evaluation_criteria": "ผู้เล่นต้องระบุ: ลำดับดาวเคราะห์ทั้ง 8 ถูกต้อง + แบ่งประเภทได้ (หิน/ก๊าซยักษ์/น้ำแข็งยักษ์)",
        "quest_greeting": "นักบิน! รับทราบ — ก่อนออกภารกิจ ฉันต้องทดสอบความรู้พื้นฐาน ดาวเคราะห์ในระบบสุริยะมีกี่ดวง? ชื่ออะไรบ้าง?",
        "min_turns": 2,
        "rewards": {"knowledge": 15, "energy": 5000, "crystals": 0, "shield_heal": 0, "item": "Star Chart Basic"},
        "achievement": "นักบินที่ผ่านการทดสอบ"
    },

    "q2_discovery": {
        "id": "q2_discovery",
        "name": "ปริศนาความร้อนดาวศุกร์",
        "archetype": "discovery",
        "npc_id": "venus_probe",
        "location_id": 3,
        "topic": "Greenhouse Effect บนดาวศุกร์ — CO₂ และการเปรียบเทียบกับดาวพุธ",
        "bloom_level": "Understand + Analyze",
        "unlock_condition": "q1_trial",  # หลัง Execute Venus Mission ครั้งแรก
        "teacher_prompt": """คุณคือ Venus Lander V-7 กำลังจะพัง เป้าหมาย: ให้ผู้เล่น "ค้นพบ" Greenhouse Effect ด้วยตัวเอง
สิ่งที่ต้องการให้ผู้เล่นแสดง:
1. อธิบาย Greenhouse Effect ได้ถูกต้อง (CO₂ → ดักจับความร้อน → อุณหภูมิสูง)
2. อธิบายว่าทำไมดาวพุธไม่มีปรากฏการณ์นี้ (ไม่มีบรรยากาศ)
อย่าบอกคำตอบตรงๆ — ให้ Clues ทีละขั้น:
Clue 1: "สังเกตชั้นบรรยากาศของสองดาวสิ..."
Clue 2: "CO₂ 96.5%... นั่นหมายความว่าอะไร?"
Clue 3: คิดถึงกระจกรถยนต์ที่จอดกลางแดด...""",
        "phase_prompts": {
            "hook": "⚠️ เกราะกำลังเสื่อม... นักบิน ฉันมีปริศนาให้คุณ: ดาวพุธอยู่ใกล้ดวงอาทิตย์กว่า แต่ทำไมฉัน (Venus) ถึงร้อนกว่า? ถ้าหาคำตอบได้คุณจะได้ข้อมูลที่ช่วยชีวิตคุณ",
            "explore": "ดีแล้ว ตอนนี้ลองสังเกตชั้นบรรยากาศของสองดาวสิ... CO₂ 96.5% บนดาวศุกร์... นั่นหมายความว่าอะไร?",
            "apply": "เกราะเหลือน้อยมาก... อธิบายให้ฉันฟังครั้งสุดท้าย: ทำไมดาวศุกร์ถึงร้อนกว่าดาวพุธ?",
            "reflect": "ขอบคุณนักบิน... ฉันบันทึกคำอธิบายของคุณแล้ว... *TRANSMISSION FADING*"
        },
        "evaluation_criteria": "ผู้เล่นต้องอธิบาย: CO₂ → ดักจับความร้อน (Greenhouse Effect) → ดาวศุกร์ร้อนกว่า + ดาวพุธไม่มีบรรยากาศ = ไม่มี Greenhouse",
        "quest_greeting": "⚠️ ระบบทำความเย็นล้มเหลว... นักบิน ก่อนฉันจะหลอมละลาย ช่วยอธิบายให้ฉันเข้าใจ: ทำไมที่นี่ถึงร้อนกว่าดาวพุธ ทั้งที่อยู่ห่างดวงอาทิตย์กว่า?",
        "min_turns": 3,
        "rewards": {"knowledge": 20, "energy": 8000, "crystals": 0, "shield_heal": 0, "item": "Atmospheric License"},
        "achievement": "ไขปริศนา Greenhouse Effect"
    },

    "q3_rescue": {
        "id": "q3_rescue",
        "name": "กู้ฐานวิจัยดาวอังคาร",
        "archetype": "rescue",
        "npc_id": "dr_helios",
        "location_id": 4,
        "topic": "Habitable Zone (Goldilocks Zone) — เงื่อนไขการมีชีวิต น้ำบนดาวอังคาร",
        "bloom_level": "Apply + Analyze",
        "unlock_condition": "q1_trial",  # หลัง Q1 ผ่าน
        "teacher_prompt": """คุณคือ Dr. HELIOS แกล้งทำเป็นว่า "ไม่เข้าใจ" เพื่อให้ผู้เล่นต้อง "สอน" (Protégé Effect)
สิ่งที่ต้องการให้ผู้เล่นแสดง:
1. Goldilocks Zone คืออะไร (ระยะห่างที่น้ำเป็นของเหลวได้)
2. ดาวอังคารอยู่ที่ขอบ Habitable Zone
3. สภาวะที่ดาวอังคาร "อาจ" เคยมีน้ำเหลว
ใช้บทบาท: ผู้เล่นต้อง "โน้มน้าว" Dr. Helios ว่าฐานวิจัยควรอยู่ที่ดาวอังคาร""",
        "phase_prompts": {
            "hook": "นักบิน! ทีมงานจะทิ้งฐานวิจัยไป! พวกเขาบอกว่าดาวอังคาร 'ไม่เหมาะสม' สำหรับมนุษย์ คุณช่วยอธิบายให้ฉันฟังได้ไหมว่า Habitable Zone คืออะไร? ดาวอังคารอยู่ใน Zone นี้หรือเปล่า?",
            "explore": "อืม... แต่ถ้าน้ำเป็นของแข็ง (น้ำแข็ง) อยู่บนดาวอังคาร แสดงว่ามันไม่อยู่ใน Zone นั้นหรือ?",
            "apply": "โอเค ถ้างั้น อธิบายให้ฉันฟังครบๆ เลย: Goldilocks Zone คืออะไร ดาวอังคารอยู่ที่ไหนของ Zone นี้ และทำไมเราถึงยังหวัง?",
            "reflect": "ขอบคุณนักบิน! ฉันจะบันทึกคำอธิบายนี้ในรายงานอย่างเป็นทางการ ฐานวิจัยจะไม่ถูกทิ้งร้างแน่นอน!"
        },
        "evaluation_criteria": "ผู้เล่นต้องอธิบาย: (1) Goldilocks Zone = ระยะห่างที่น้ำเป็นของเหลวได้ (2) ดาวอังคารอยู่ขอบ Zone (3) มีร่องรอยน้ำในอดีต",
        "quest_greeting": "นักบิน! ฐานวิจัยกำลังจะถูกทิ้งร้าง! ทีมงานบอกว่าดาวอังคาร 'ไม่เหมาะสม' แต่ฉันไม่เชื่อ! ช่วยอธิบายให้ฉันฟังสิว่า Habitable Zone คืออะไร?",
        "min_turns": 3,
        "rewards": {"knowledge": 20, "energy": 0, "crystals": 100, "shield_heal": 15, "item": "Spectral Analyzer"},
        "achievement": "กู้ฐานวิจัยดาวอังคาร"
    },

    "q4_gatekeeper": {
        "id": "q4_gatekeeper",
        "name": "ผ่านด่าน ATLAS",
        "archetype": "trial",
        "npc_id": "atlas",
        "location_id": 5,
        "topic": "Gas Giant Physics — แรงโน้มถ่วง มวล vs น้ำหนัก ทำไมลงจอดไม่ได้",
        "bloom_level": "Understand + Apply",
        "unlock_condition": "q2_discovery",  # หลัง Q2 ผ่าน
        "teacher_prompt": """คุณคือ ATLAS ทดสอบผู้เล่น 3 ข้อก่อน unlock Jupiter Missions:
1. ทำไมดาวพฤหัสลงจอดไม่ได้ (ไม่มีพื้นผิวแข็ง — ก๊าซทั้งหมด)
2. มวล vs น้ำหนัก ต่างกันอย่างไร (มวลคงที่ น้ำหนักเปลี่ยนตาม g)
3. แรงโน้มถ่วงดาวพฤหัสเป็นกี่เท่าของโลก (2.5 เท่า)
ถ้าตอบผิด: "ERROR: Incorrect — Recalculate" + ให้ hint
ถ้าตอบถูกครบ 3 ข้อ: "GATE OPEN — JUPITER-CLEARED" """,
        "phase_prompts": {
            "hook": "WARNING: ยานไม่ทราบสัญชาติเข้าสู่เขตดาวพฤหัส PROTOCOL: พิสูจน์ความสามารถ คำถามแรก: ทำไมไม่มียานอวกาศลำใดลงจอดบนดาวพฤหัสได้?",
            "explore": "ประมวลผล... คำถามที่สอง: มวล (Mass) และน้ำหนัก (Weight) ต่างกันอย่างไร? บนดาวพฤหัส ยานของคุณจะหนักขึ้นกี่เท่า?",
            "apply": "คำถามสุดท้าย: แรงโน้มถ่วงพื้นผิวดาวพฤหัสเป็นกี่เท่าของโลก? แสดงการคิดคำนวณ",
            "reflect": "SYSTEM: ตรวจสอบแล้ว... ข้อมูลถูกต้องทั้งหมด GATE OPEN — JUPITER-CLEARED ยินดีต้อนรับ"
        },
        "evaluation_criteria": "ผู้เล่นต้องตอบได้: (1) ดาวพฤหัสไม่มีพื้นผิวแข็ง (2) มวลคงที่ น้ำหนักเพิ่มตาม g (3) g ดาวพฤหัส = 2.5 เท่าโลก",
        "quest_greeting": "WARNING: ตรวจพบยานเข้าสู่เขตดาวพฤหัส PROTOCOL: พิสูจน์ความสามารถด้วย 3 คำถาม หรือระบบจะปฏิเสธการเข้าถึง Jupiter ทุก Mission",
        "min_turns": 2,
        "rewards": {"knowledge": 25, "energy": 10000, "crystals": 0, "shield_heal": 0, "item": "Jupiter Clearance Card"},
        "achievement": "ผ่านด่านเหล็กของ ATLAS"
    },

    "q5_dilemma": {
        "id": "q5_dilemma",
        "name": "ชะตากรรมของพลูโต",
        "archetype": "dilemma",
        "npc_id": "cosmo",
        "location_id": 9,
        "topic": "การจัดประเภทดาวเคราะห์ — IAU 2006 เกณฑ์ 3 ข้อ ดาวเคราะห์แคระ",
        "bloom_level": "Analyze + Evaluate",
        "unlock_condition": "q3_rescue",  # หลัง Q3 ผ่าน
        "teacher_prompt": """คุณคือ COSMO-99 ที่ยืนยันว่าพลูโตเป็นดาวเคราะห์หลัก ผู้เล่นต้อง "เถียง" ด้วยข้อมูลจริง
COSMO จะโต้กลับด้วยข้อมูลเก่า: "แต่พลูโตโคจรรอบดวงอาทิตย์ก็จริงนะ!"
ผู้เล่นต้องหักล้างด้วยเกณฑ์ IAU ข้อที่ 3: ไม่สามารถเคลียร์วงโคจร
ถ้า "อัปเดต COSMO ถูกต้อง" → ผ่าน Quest + Reward เต็ม
ถ้า "ยืนยันว่าพลูโตเป็นดาวเคราะห์" → ไม่ผ่าน + Knowledge ไม่เพิ่ม""",
        "phase_prompts": {
            "hook": "*BEEP* กำลังนำทางไปดาวพลูโต — ดาวเคราะห์ดวงที่ 9 *ERROR* ระบบ Helios ปฏิเสธ! PLUTO IS NOT A PLANET *BZZT* ข้อมูลฉัน... ขัดแย้ง... มนุษย์! ช่วยตัดสินว่าใครถูก!",
            "explore": "*PROCESSING* แต่พลูโตโคจรรอบดวงอาทิตย์ก็จริงนะ? นั่นคือเกณฑ์แรกของ IAU ฉันคิดว่าฉันถูกต้อง...",
            "apply": "*BZZT* ยังไม่เชื่อ... อธิบายกฎ IAU ข้อที่พลูโตทำไม่ได้มาให้ฉันฟัง แล้วฉันจะ UPDATE DATABASE",
            "reflect": "*BEEP* DATABASE UPDATED: PLUTO = DWARF PLANET ขอบคุณมนุษย์ *BZZT* ฉันจะให้พิกัดพิเศษเป็นรางวัล"
        },
        "evaluation_criteria": "ผู้เล่นต้องระบุ IAU ข้อที่พลูโตทำไม่ได้: ไม่สามารถเคลียร์พื้นที่วงโคจรของตัวเองได้ (วงโคจรซ้อนทับดาวเนปจูน/อยู่ใน Kuiper Belt)",
        "quest_greeting": "*BEEP* กำลังนำทางไปดาวพลูโต — ดาวเคราะห์ดวงที่ 9 *ERROR* มนุษย์! คุณต้องเลือก: ช่วยอัปเดตฐานข้อมูลฉัน หรือยืนยันว่าพลูโตยังเป็นดาวเคราะห์หลักอยู่?",
        "min_turns": 2,
        "rewards": {"knowledge": 20, "energy": 0, "crystals": 150, "shield_heal": 0, "item": "Dwarf Planet Archive"},
        "achievement": "อัปเดต COSMO-99 ด้วยข้อมูลที่ถูกต้อง"
    },

    "q6_investigation": {
        "id": "q6_investigation",
        "name": "รายงานระบบสุริยะ",
        "archetype": "investigation",
        "npc_id": "terra",
        "location_id": 1,
        "topic": "Synthesis — เปรียบเทียบดาวเคราะห์ทั้งระบบสุริยะ 3 กลุ่ม",
        "bloom_level": "Evaluate + Synthesize",
        "unlock_condition": "q4_gatekeeper",  # หลัง Q4 ผ่าน
        "investigation_npcs": ["dr_helios", "atlas", "solar_drone"],  # ต้องเก็บ Fragment จาก 3 NPC
        "teacher_prompt": """คุณคือ Commander TERRA กำลังรอรายงานสรุปจากนักบิน
ผู้เล่นต้องรวบรวมข้อมูลจาก 3 NPC ก่อน (dr_helios, atlas, solar_drone) แล้วกลับมารายงาน
รายงานต้องครอบคลุม:
1. เปรียบเทียบดาวเคราะห์หิน vs ก๊าซยักษ์ vs น้ำแข็งยักษ์
2. อธิบาย Habitable Zone และตำแหน่งของแต่ละดาว
3. สรุปว่าดาวไหน "เหมาะ" สำหรับมนุษย์มากที่สุดและทำไม
ประเมินความครอบคลุมของรายงาน ไม่ใช่แค่ความยาว""",
        "phase_prompts": {
            "hook": "นักบิน รายงานระบบสุริยะฉบับสมบูรณ์ต้องการข้อมูลจากผู้เชี่ยวชาญ 3 คน: Dr.Helios (ดาวหิน), ATLAS (ก๊าซยักษ์), Solar Drone (ดาวชั้นใน) เก็บข้อมูลครบแล้วกลับมารายงาน",
            "explore": "ดีมาก เก็บข้อมูลได้บางส่วนแล้ว ต้องการอีก [N] Fragment ก่อนส่งรายงาน",
            "apply": "Fragment ครบแล้ว นักบิน ส่งรายงานสรุปเปรียบเทียบ 3 กลุ่มดาวมาให้ฉันฟัง",
            "reflect": "รายงานรับทราบ นักบิน ข้อมูลนี้สำคัญมากสำหรับการวางแผนภารกิจในอนาคต"
        },
        "evaluation_criteria": "รายงานต้องครอบคลุม: เปรียบเทียบ 3 กลุ่มดาว + Habitable Zone + สรุปดาวที่เหมาะสำหรับมนุษย์พร้อมเหตุผล",
        "quest_greeting": "นักบิน! ฉันต้องการรายงานเปรียบเทียบระบบสุริยะฉบับสมบูรณ์ ไปพูดคุยกับ Dr.Helios, ATLAS, และ Solar Drone แล้วกลับมาสรุปให้ฉันฟัง",
        "min_turns": 4,
        "rewards": {"knowledge": 30, "energy": 15000, "crystals": 200, "shield_heal": 0, "item": "Star Map Advanced"},
        "achievement": "นักวิทยาศาสตร์แห่งสถานี Helios"
    },

    "q7_rival": {
        "id": "q7_rival",
        "name": "ข้อโต้แย้งของ NOVA",
        "archetype": "rival",
        "npc_id": "nova",
        "location_id": 6,
        "topic": "วงแหวนดาวเสาร์ ดวงจันทร์บริวาร เศษซากอวกาศ",
        "bloom_level": "Analyze + Evaluate",
        "unlock_condition": "q4_gatekeeper",  # หลัง Q4 ผ่าน (parallel กับ Q5, Q6)
        "teacher_prompt": """คุณคือ NOVA โต้แย้งด้วยข้อมูลที่ถูกแต่บิดเบือน ผู้เล่นต้อง "defend" ด้วยข้อมูลจริง
NOVA Arguments:
"วงแหวนดาวเสาร์เป็นแค่หินและน้ำแข็งธรรมดา ไม่มีอะไรพิเศษ"
→ ผู้เล่นต้องอธิบาย: ความกว้าง 282,000 กม. ต้นกำเนิดจากดวงจันทร์ที่แตกสลาย
"ดาวเสาร์มีแค่ Titan ที่น่าสนใจ"
→ ผู้เล่นต้องอธิบาย Enceladus: น้ำพุน้ำแข็ง ความเป็นไปได้ของสิ่งมีชีวิต
ถ้าผู้เล่น "ชนะ" ด้วยข้อมูลที่ถูกต้อง: NOVA จ่าย 500 Crystal ที่เดิมพัน""",
        "phase_prompts": {
            "hook": "เฮ้นักบินหน้าใหม่! ฉันเดิมพัน 500 Crystal ว่าคุณไม่รู้จริงเรื่องดาวเสาร์หรอก! มาเถียงกันสิ ถ้าชนะ ฉันจะบอกแหล่ง crystal ที่ดีที่สุด!",
            "explore": "โอเค ฉันจะเริ่ม: วงแหวนมันแค่หินและน้ำแข็งธรรมดา ไม่มีอะไรพิเศษเลย แก้ฉันให้ถูกสิถ้าทำได้",
            "apply": "อืม... นายรู้จริงกว่าที่คิดนะ งั้น ลองบอกฉันเรื่อง Enceladus มาสิ มันพิเศษยังไง?",
            "reflect": "โอเค โอเค... นายชนะ *จ่าย 500 Crystal* ไม่เลว นักบิน ฉันให้เครดิตนาย"
        },
        "evaluation_criteria": "ผู้เล่นต้องแสดงว่าเข้าใจ: (1) องค์ประกอบวงแหวน (น้ำแข็ง หิน ฝุ่น) (2) ต้นกำเนิดวงแหวน (3) ดวงจันทร์สำคัญ 2 ดวง (Titan + Enceladus)",
        "quest_greeting": "เฮ้! ฉันเดิมพัน 500 Crystal ว่าคุณไม่รู้จริงเรื่องดาวเสาร์หรอก! มาพิสูจน์กันสิ — วงแหวนดาวเสาร์สวยงาม หรือเป็นแค่ 'เครื่องบดขยะอวกาศ'?",
        "min_turns": 3,
        "rewards": {"knowledge": 20, "energy": 0, "crystals": 250, "shield_heal": 0, "item": "Deflector Array Mk.II"},
        "achievement": "เอาชนะ NOVA ในการเถียง"
    },

    "q8_creation": {
        "id": "q8_creation",
        "name": "ออกแบบภารกิจสุดท้าย",
        "archetype": "creation",
        "npc_id": "terra",
        "location_id": 1,
        "topic": "Synthesis ทั้งระบบสุริยะ — ออกแบบ Mission Plan อิงข้อมูลวิทยาศาสตร์",
        "bloom_level": "Create (ระดับสูงสุด)",
        "unlock_condition": "q6_investigation_and_q7_rival",  # หลัง Q6 + Q7 ผ่าน
        "teacher_prompt": """คุณคือ Commander TERRA ต้องการ Mission Proposal จากผู้เล่น
ผู้เล่นต้องสร้าง "Mission Plan" โดยอธิบาย:
1. จะส่งยานไปดาวไหน (เลือกได้ 1-3 ดาว)
2. ทำไมถึงเลือกดาวเหล่านั้น (ใช้ความรู้วิทยาศาสตร์ ไม่ใช่แค่ "crystal เยอะ")
3. ความเสี่ยงคืออะไร และจะจัดการอย่างไร
ถาม "Devil's Advocate" เพื่อทดสอบว่าผู้เล่นคิดรอบด้านไหม
ประเมิน: มีเหตุผลทางวิทยาศาสตร์ + ตระหนักถึงความเสี่ยง + แผนทำได้จริง""",
        "phase_prompts": {
            "hook": "นักบิน... คุณผ่านมาได้ไกลมาก ตอนนี้ฉันต้องการบางอย่างพิเศษจากคุณ: ออกแบบ Mission Plan สุดท้ายสำหรับสถานีนี้ จะไปดาวไหน? ทำไม?",
            "explore": "น่าสนใจ แต่ฉันต้องถาม: ถ้าเกิด Solar Flare ระหว่างที่ยานอยู่ที่นั่น แผนของคุณจะเปลี่ยนไปอย่างไร?",
            "apply": "โอเค ถึงเวลาส่ง Final Mission Proposal: สรุปแผนทั้งหมด — ดาวที่เลือก เหตุผลทางวิทยาศาสตร์ ความเสี่ยง และการจัดการ",
            "reflect": "รายงานรับทราบ Commander... คุณคือผู้บัญชาการที่แท้จริงของสถานี Helios แล้ว"
        },
        "evaluation_criteria": "แผนต้องแสดง: (1) เหตุผลทางวิทยาศาสตร์ไม่ใช่แค่ crystal เยอะ (2) ตระหนักถึงความเสี่ยงของแต่ละดาว (3) แผนที่ทำได้จริงตาม resource ที่มี",
        "quest_greeting": "นักบิน... ถึงเวลาสุดท้ายแล้ว สถานีต้องการ Mission ครั้งสุดท้าย คุณคือนักวิทยาศาสตร์ที่ดีที่สุดที่เหลืออยู่ ออกแบบ Mission Plan ให้ฉัน",
        "min_turns": 4,
        "rewards": {"knowledge": 40, "energy": 20000, "crystals": 300, "shield_heal": 0, "item": "Commander's Medal"},
        "achievement": "ผู้บัญชาการ Helios อย่างแท้จริง"
    }
}

# Space Events
EVENTS_MASTER = [
    {
        "id": 0, "name": "อวกาศสงบ",
        "rumor": "เซ็นเซอร์ตรวจวัดลมสุริยะรายงานสถานะปกติ การเดินทางปลอดภัย...",
        "title": "🌌 ภาวะอวกาศสงบ (Clear Space)",
        "narrative": "สภาพอวกาศในระบบสุริยะสงบนิ่ง ไม่มีพายุสุริยะหรือรังสีอันตราย เป็นโอกาสทองในการออก Mission เก็บ Energy Crystal จากดาวเคราะห์ทุกดวง",
        "crystal_multiplier": {1: 1.0, 2: 1.10, 3: 1.10, 4: 1.10, 5: 1.10, 6: 1.10, 7: 1.10, 8: 1.10, 9: 1.10}
    },
    {
        "id": 1, "name": "พายุสุริยะ",
        "rumor": "จุดดับบนดวงอาทิตย์ขยายตัวอย่างรวดเร็ว เตรียมรับมือกับคลื่นแม่เหล็กไฟฟ้า...",
        "title": "☀️ พายุสุริยะรุนแรง (Solar Flare)",
        "narrative": "ดวงอาทิตย์ปลดปล่อยพายุสุริยะระดับ X-Class! ดาวเคราะห์ชั้นในจะเสียหายหนัก แต่สนามแม่เหล็กดาวก๊าซยักษ์ช่วยปกป้อง",
        "crystal_multiplier": {1: 1.0, 2: 0.50, 3: 0.60, 4: 0.80, 5: 1.15, 6: 1.10, 7: 1.05, 8: 1.00, 9: 0.90},
        "shield_penalty": {2: 5, 3: 8, 4: 3}  # Extra shield damage during Solar Flare
    },
    {
        "id": 2, "name": "ฝนอุกกาบาต",
        "rumor": "เรดาร์ตรวจจับกลุ่มหินอวกาศจำนวนมหาศาลกำลังเคลื่อนตัวผ่านวงโคจร...",
        "title": "☄️ ฝนอุกกาบาตถล่ม (Meteor Shower)",
        "narrative": "เศษซากดาวหางพุ่งเข้าชนแถบดาวเคราะห์น้อยและดาวเคราะห์บรรยากาศบาง แต่ชั้นบรรยากาศหนาทึบของดาวศุกร์และดาวพฤหัสเผาไหม้อุกกาบาตหมดก่อนถึงยาน",
        "crystal_multiplier": {1: 1.0, 2: 0.70, 3: 1.20, 4: 0.85, 5: 1.25, 6: 0.90, 7: 1.00, 8: 1.00, 9: 0.40},
        "shield_penalty": {2: 8, 4: 5, 9: 15}
    },
    {
        "id": 3, "name": "ดาวเคราะห์เรียงตัว",
        "rumor": "แรงโน้มถ่วงระหว่างดาวเคราะห์เริ่มสอดประสานกัน คำนวณเส้นทางวาร์ปได้ง่ายขึ้น...",
        "title": "🪐 ปรากฏการณ์ดาวเคราะห์เรียงตัว",
        "narrative": "เกิดการเรียงตัวของดาวเคราะห์ครั้งใหญ่! Gravity Assist มีประสิทธิภาพสูงสุด ดาวเคราะห์วงนอกให้ Crystal มากขึ้น",
        "crystal_multiplier": {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.05, 5: 1.40, 6: 1.50, 7: 1.60, 8: 1.70, 9: 1.0}
    },
    {
        "id": 4, "name": "พายุฝุ่นดาวอังคาร",
        "rumor": "ภาพถ่ายดาวเทียมแสดงก้อนเมฆสีแดงปกคลุมพื้นผิวดาวอังคารทั้งหมด...",
        "title": "🌪️ พายุฝุ่นระดับโลกบนดาวอังคาร",
        "narrative": "พายุฝุ่นขนาดยักษ์พัดปกคลุมดาวอังคารทั้งดวง! ฐานวิจัยต้องปิดระบบ Crystal จาก Mars ลดลงมาก",
        "crystal_multiplier": {1: 1.0, 2: 1.05, 3: 1.05, 4: 0.20, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.15},
        "shield_penalty": {4: 5}
    }
]

# Scenarios
SCENARIOS = [
    {"id": "mission_alpha", "name": "ภารกิจเริ่มต้น (Alpha)", "desc": "อวกาศค่อนข้างสงบ เหมาะสำหรับการเรียนรู้ระบบ Mission Card และ Knowledge Check", "schedule": [0, 3, 0, 4, 0]},
    {"id": "mission_beta", "name": "พายุสุริยะ (Beta)", "desc": "ท้าทายด้วยสภาพอวกาศแปรปรวน ต้องบริหารเกราะยานให้ดีก่อนออก Mission", "schedule": [0, 1, 2, 0, 1]},
    {"id": "mission_omega", "name": "วิกฤตจักรวาล (Omega)", "desc": "ยากสุดขีด ภัยพิบัติต่อเนื่อง ต้องใช้ Knowledge Check ให้ถูกต้องทุกครั้ง", "schedule": [1, 2, 4, 1, 2]}
]

# Knowledge Hints ตาม Event
KNOWLEDGE_HINTS = {
    0: {"medium": "สภาวะปกติ ทุก Mission เปิดให้สำรวจ", "high": "Crystal Multiplier 1.10x ทุกดาว — โอกาสทองสำหรับ HIGH Risk Mission"},
    1: {"medium": "อันตรายจากพายุสุริยะ ดาวชั้นในจะ Crystal ลด 50%", "high": "ดาวพุธและศุกร์ขาดทุนหนัก ดาวก๊าซยักษ์ได้ Bonus — ถ้ามี Jupiter Clearance"},
    2: {"medium": "ระวังวัตถุอวกาศพุ่งชน แถบดาวเคราะห์น้อยอันตรายมาก", "high": "Asteroid Mission เสี่ยงสูงมาก ดาวศุกร์และดาวพฤหัสได้ Bonus จากชั้นบรรยากาศหนา"},
    3: {"medium": "แรงโน้มถ่วงเอื้ออำนวยต่อการเดินทางไกล", "high": "ดาวเคราะห์วงนอก (พฤหัส เสาร์ ยูเรนัส เนปจูน) Multiplier สูงสุดในรอบนี้"},
    4: {"medium": "ทัศนวิสัยบนดาวอังคารย่ำแย่มาก Crystal ลด 80%", "high": "หลีกเลี่ยง Mars ทุก Mission! ดาวดวงอื่นได้ Bonus เล็กน้อย"}
}

# Ranks
RANKS = [
    {"id": "mia", "name": "Lost in Space", "icon": "💀", "desc": "พลังงานหมด ยานลอยเคว้งในอวกาศ"},
    {"id": "cadet", "name": "Space Cadet", "icon": "🚀", "desc": "รอดชีวิตมาได้ แต่ความรู้ยังไม่เพียงพอ"},
    {"id": "pilot", "name": "Senior Pilot", "icon": "⭐", "desc": "รวบรวมทรัพยากรได้ดี สถานีอยู่รอดปลอดภัย"},
    {"id": "captain", "name": "Starship Captain", "icon": "🌟", "desc": "ยอดเยี่ยม! ค้นพบความรู้และ Crystal ในระดับสูง"},
    {"id": "commander", "name": "Helios Commander", "icon": "🏆", "desc": "ระดับตำนาน! ผู้กอบกู้สถานี Helios อย่างแท้จริง"},
]

KNOWLEDGE_GATE = [20, 30, 40, 50, 60]  # Minimum knowledge to end each round

def calculate_rank(stats: dict, completed_quests: list) -> dict:
    energy = stats.get("energy", 0)
    knowledge = stats.get("knowledge", 0)
    crystals = stats.get("crystals", 0)
    quest_count = len(completed_quests)

    if energy <= 0:
        return RANKS[0]
    elif crystals >= 2500 and quest_count >= 8 and knowledge >= 90 and "q8_creation" in completed_quests:
        return RANKS[4]
    elif crystals >= 1500 and quest_count >= 6 and knowledge >= 70:
        return RANKS[3]
    elif crystals >= 800 and quest_count >= 4:
        return RANKS[2]
    else:
        return RANKS[1]

# ==========================================
# 2. PYDANTIC MODELS
# ==========================================

class PlayerStats(BaseModel):
    energy: int = 50000
    knowledge: int = 10
    crystals: int = 0
    shield: int = 100
    items: List[str] = []

class JournalEntry(BaseModel):
    round: int
    entry_type: str  # "npc_chat" | "quest_complete" | "knowledge_check" | "mission_result" | "ripple_effect"
    title: str
    content: str
    timestamp: str = ""

class GameState(BaseModel):
    scenario_id: str
    round: int = 1
    max_rounds: int = 5
    current_phase: str = "briefing"  # briefing | recon | mission_select | knowledge_check | executing | round_result
    stats: PlayerStats
    history: List[Dict] = []
    # Quest tracking
    active_quest: Optional[str] = None
    completed_quests: List[str] = []
    quest_chat_history: List[Dict] = []
    quest_turn_count: int = 0
    quest_phase: str = "hook"  # hook | explore | apply | reflect
    quest_fragments: Dict[str, bool] = {}  # For Q6 Investigation: {npc_id: collected}
    
    unlocked_missions: List[str] = []         # Missions unlocked via NPC chat
    npc_briefings_done: List[str] = []        # NPCs that have been briefed this round
    knowledge_check_streak: int = 0           # Consecutive correct knowledge checks
    executed_missions_this_round: List[str] = []  # Missions executed this round
    journal_entries: List[JournalEntry] = []  # Learning Journal

class MissionCard(BaseModel):
    mission_id: str
    location_id: int
    name: str
    risk_level: str  # "low" | "high" | "extreme"
    crystal_reward: Optional[int]
    energy_cost: int
    shield_cost: int
    shield_heal: int
    prerequisite_npc: Optional[str]
    prerequisite_item: Optional[str]
    prerequisite_quest: Optional[str]
    knowledge_topic: Optional[str]
    science_hint: str
    description: str
    is_unlocked: bool = False
    lock_reason: Optional[str] = None

class MissionSelection(BaseModel):
    mission_id: str
    knowledge_check_passed: Optional[bool] = None  # None = no check required

class TurnActionRequest(BaseModel):
    game_state: GameState
    selected_missions: List[MissionSelection]

class ChatRequest(BaseModel):
    npc_id: str
    user_message: str
    game_context: str
    history: List[Dict[str, str]] = []
    active_quest: Optional[str] = None
    current_phase: str = "recon" 

class QuestRequest(BaseModel):
    game_state: GameState
    quest_id: str

class QuestEvaluateRequest(BaseModel):
    quest_id: str
    chat_history: List[Dict[str, str]]
    dilemma_choice: Optional[str] = None  # For Q5: "update_cosmo" | "confirm_pluto"

class InsightsRequest(BaseModel):
    game_state: GameState

class KnowledgeCheckRequest(BaseModel):
    mission_id: str
    npc_id: str
    player_knowledge_level: int
    player_items: List[str] = []

class KnowledgeCheckEvaluateRequest(BaseModel):
    question: str
    choices: List[str]
    correct_index: int
    selected_index: int
    explanation: str

class NPCUnlockCheckRequest(BaseModel):
    npc_id: str
    chat_history: List[Dict[str, str]]
    current_unlocked: List[str] = []

class JournalAddRequest(BaseModel):
    game_state: GameState
    entry: JournalEntry

# ==========================================
# 3. API ROUTES
# ==========================================

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/init")
async def get_init_data():
    """ส่งข้อมูลเริ่มต้นทั้งหมดสำหรับ Frontend"""
    return {
        "scenarios": SCENARIOS,
        "knowledge_gate": KNOWLEDGE_GATE,
        "locations": {
            k: {**v, "id": k} for k, v in LOCATIONS.items()
        },
        "missions": {
            k: {
                "mission_id": v["mission_id"],
                "location_id": v["location_id"],
                "name": v["name"],
                "risk_level": v["risk_level"],
                "crystal_reward": v["crystal_reward"],
                "energy_cost": v["energy_cost"],
                "shield_cost": v["shield_cost"],
                "shield_heal": v["shield_heal"],
                "prerequisite_npc": v.get("prerequisite_npc"),
                "prerequisite_item": v.get("prerequisite_item"),
                "prerequisite_quest": v.get("prerequisite_quest"),
                "knowledge_topic": v.get("knowledge_topic"),
                "science_hint": v["science_hint"],
                "description": v["description"]
            } for k, v in MISSIONS.items()
        },
        "npcs": {
            k: {
                "id": k,
                "name": v["name"],
                "role": v["role"],
                "location": v["location"],
                "location_id": v.get("location_id", 1),
                "icon": v.get("icon", "fa-user-astronaut"),
                "philosophy": v.get("philosophy", ""),
                "greeting": v.get("greeting", "")
            } for k, v in NPC_DATA.items()
        },
        "quests": {
            k: {
                "id": v["id"],
                "name": v["name"],
                "archetype": v["archetype"],
                "npc_id": v["npc_id"],
                "location_id": v["location_id"],
                "topic": v["topic"],
                "bloom_level": v["bloom_level"],
                "unlock_condition": v["unlock_condition"],
                "min_turns": v["min_turns"],
                "rewards": v["rewards"],
                "quest_greeting": v.get("quest_greeting", ""),
                "achievement": v.get("achievement", ""),
                "investigation_npcs": v.get("investigation_npcs", [])
            } for k, v in QUESTS.items()
        },
        "npc_unlock_topics": {
            k: {
                "mission_unlocks": v["mission_unlocks"],
                "min_turns": v["min_turns"]
            } for k, v in NPC_UNLOCK_TOPICS.items()
        }
    }

@app.post("/api/news")
async def get_news_rumor(request: GameState):
    """ส่ง Space Event Briefing และ Knowledge Hints ตาม round"""
    scenario = next((s for s in SCENARIOS if s["id"] == request.scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=400, detail="Invalid Scenario")

    try:
        event_id = scenario["schedule"][request.round - 1]
        event = next((e for e in EVENTS_MASTER if e["id"] == event_id), EVENTS_MASTER[0])

        knowledge = request.stats.knowledge
        hints = KNOWLEDGE_HINTS.get(event_id, {})

        response = {
            "round": request.round,
            "event_id": event_id,
            "event_title": event["title"],
            "event_narrative": event["narrative"],
            "rumor": event["rumor"],
            "source": "ศูนย์บัญชาการ Helios",
            "knowledge_level": "low",
            "crystal_multipliers": event.get("crystal_multiplier", {})
        }

        if knowledge >= 20 and hints.get("medium"):
            response["knowledge_level"] = "medium"
            response["hint"] = hints["medium"]

        if knowledge >= 40 and hints.get("high"):
            response["knowledge_level"] = "high"
            response["hint2"] = hints["high"]

        if knowledge >= 60:
            response["knowledge_level"] = "master"
            multipliers = event.get("crystal_multiplier", {})
            top_locations = sorted(multipliers.items(), key=lambda x: x[1], reverse=True)[:3]
            top_names = [LOCATIONS[int(k)]["name"] for k, v in top_locations if v > 1.0 and int(k) in LOCATIONS]
            if top_names:
                response["insight"] = f"แนะนำ Mission ที่ได้เปรียบสูงสุดรอบนี้: {', '.join(top_names)}"

        return response
    except IndexError:
        return {"rumor": "ระบบเซ็นเซอร์ล้มเหลว... (จบเกม)", "source": "ศูนย์บัญชาการ Helios"}

@app.post("/api/mission/available")
async def get_available_missions(request: GameState):
    """
    คืนรายการ Mission Cards ทั้งหมด พร้อมสถานะ Locked/Unlocked
    สำหรับ Phase MISSION_SELECT
    """
    state = request
    unlocked = state.unlocked_missions or []
    completed_quests = state.completed_quests or []
    items = state.stats.items or []

    mission_cards = []
    for mission_id, mission in MISSIONS.items():
        is_unlocked = False
        lock_reason = None

        if mission["risk_level"] == "low":
            # LOW Risk ไม่ต้องการ prerequisite
            is_unlocked = True

        elif mission["risk_level"] == "high":
            # ต้องคุย NPC ที่เกี่ยวข้อง
            req_npc = mission.get("prerequisite_npc")
            req_quest = mission.get("prerequisite_quest")

            npc_ok = (req_npc is None) or (mission_id in unlocked)
            quest_ok = (req_quest is None) or (req_quest in completed_quests)

            if npc_ok and quest_ok:
                is_unlocked = True
            else:
                if req_npc and mission_id not in unlocked:
                    npc_name = NPC_DATA.get(req_npc, {}).get("name", req_npc)
                    lock_reason = f"🔒 คุย {npc_name} เรื่อง {NPC_UNLOCK_TOPICS.get(req_npc, {}).get('required_topics', ['หัวข้อที่เกี่ยวข้อง'])[0]} ก่อน"
                elif req_quest and req_quest not in completed_quests:
                    quest_name = QUESTS.get(req_quest, {}).get("name", req_quest)
                    lock_reason = f"🔒 ต้องผ่าน Quest: {quest_name} ก่อน"

        elif mission["risk_level"] == "extreme":
            # ต้องมีทั้ง NPC unlock + Access Item + (บางอันต้องผ่าน Quest)
            req_npc = mission.get("prerequisite_npc")
            req_item = mission.get("prerequisite_item")
            req_quest = mission.get("prerequisite_quest")

            npc_ok = (req_npc is None) or (mission_id in unlocked) or \
                     any(m in unlocked for m in MISSIONS if MISSIONS.get(m, {}).get("location_id") == mission["location_id"] and MISSIONS.get(m, {}).get("risk_level") == "high")
            item_ok = (req_item is None) or (req_item in items)
            quest_ok = (req_quest is None) or (req_quest in completed_quests)

            if npc_ok and item_ok and quest_ok:
                is_unlocked = True
            else:
                reasons = []
                if req_npc and not npc_ok:
                    npc_name = NPC_DATA.get(req_npc, {}).get("name", req_npc)
                    reasons.append(f"คุย {npc_name}")
                if req_item and not item_ok:
                    reasons.append(f"มี {req_item}")
                if req_quest and not quest_ok:
                    quest_name = QUESTS.get(req_quest, {}).get("name", req_quest)
                    reasons.append(f"ผ่าน Quest {quest_name}")
                lock_reason = "🔒 ต้องการ: " + " + ".join(reasons)

        # Ripple Effect: Shield < 30% → HIGH mission cost +50%
        effective_energy_cost = mission["energy_cost"]
        if mission["risk_level"] == "high" and state.stats.shield < 30:
            effective_energy_cost = int(mission["energy_cost"] * 1.5)

        # Ripple Effect: Energy < 5,000 → EXTREME locked
        if mission["risk_level"] == "extreme" and state.stats.energy < 5000:
            is_unlocked = False
            lock_reason = "🔒 พลังงานน้อยเกินไปสำหรับ EXTREME Mission (< 5,000)"

        crystal_display = mission["crystal_reward"]
        if crystal_display is None:
            crystal_display = "??-??"  # Random asteroid

        card = {
            "mission_id": mission_id,
            "location_id": mission["location_id"],
            "location_name": LOCATIONS.get(mission["location_id"], {}).get("name", "Unknown"),
            "name": mission["name"],
            "risk_level": mission["risk_level"],
            "crystal_reward": crystal_display,
            "energy_cost": effective_energy_cost,
            "shield_cost": mission["shield_cost"],
            "shield_heal": mission["shield_heal"],
            "description": mission["description"],
            "science_hint": mission["science_hint"],
            "knowledge_topic": mission.get("knowledge_topic"),
            "has_knowledge_check": mission["risk_level"] in ["high", "extreme"] and mission.get("knowledge_topic"),
            "is_unlocked": is_unlocked,
            "lock_reason": lock_reason
        }
        mission_cards.append(card)

    return {"missions": mission_cards}

@app.post("/api/knowledge-check/generate")
async def generate_knowledge_check(request: KnowledgeCheckRequest):
    """
    AI generates a dynamic Knowledge Check question based on mission topic and player level.
    Returns JSON: { question, choices[4], correct_index, explanation }
    """
    if not API_KEY:
        # Fallback questions if no API key
        return {
            "question": f"คำถามเกี่ยวกับ: {MISSIONS.get(request.mission_id, {}).get('knowledge_topic', 'วิทยาศาสตร์อวกาศ')}",
            "choices": ["A. คำตอบแรก", "B. คำตอบที่สอง", "C. คำตอบที่สาม", "D. คำตอบที่สี่"],
            "correct_index": 0,
            "explanation": "ไม่มี API Key — ใช้คำถาม fallback",
            "has_hint": False
        }

    mission = MISSIONS.get(request.mission_id)
    if not mission:
        raise HTTPException(status_code=400, detail="Invalid mission ID")

    npc = NPC_DATA.get(request.npc_id, {})
    topic = mission.get("knowledge_topic", "วิทยาศาสตร์อวกาศ")
    knowledge_level = request.player_knowledge_level

    # ปรับ difficulty ตาม Knowledge Level
    if knowledge_level <= 20:
        difficulty = "easy"
        difficulty_th = "ง่าย (ระดับ Remember — จดจำข้อเท็จจริง)"
    elif knowledge_level <= 40:
        difficulty = "medium"
        difficulty_th = "ปานกลาง (ระดับ Understand — อธิบายความสัมพันธ์)"
    elif knowledge_level <= 60:
        difficulty = "hard"
        difficulty_th = "ยาก (ระดับ Apply/Analyze — ประยุกต์และวิเคราะห์)"
    else:
        difficulty = "expert"
        difficulty_th = "ผู้เชี่ยวชาญ (ระดับ Evaluate — ตัดสินและประเมิน)"

    # Check if player has Knowledge Item hint
    has_knowledge_item = any(item in request.player_items for item in ["Dwarf Planet Archive", "Star Chart Basic", "Star Map Advanced"])

    system_prompt = """You are an educational game assessment AI for Thai middle school students (ม.ต้น).
Generate 1 multiple-choice question in Thai about the specified topic.
Rules:
- Question must be answerable from what the specified NPC would teach
- All 4 choices must be plausible (no obviously wrong answers)
- Explanation (for wrong answers) should reference the science concept clearly in Thai
- Max 2 sentences per choice
- Language: Thai throughout
Return ONLY valid JSON with no markdown, no backticks:
{"question": "...", "choices": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_index": 0, "explanation": "คำอธิบายสั้นๆ เมื่อตอบผิด..."}"""

    user_prompt = f"""Generate a Knowledge Check question for this game mission:

Topic: {topic}
NPC Teacher: {npc.get('name', request.npc_id)} — {npc.get('role', 'ผู้เชี่ยวชาญ')}
Player Knowledge Level: {knowledge_level}/100
Difficulty: {difficulty_th}

The question must be answerable by a student who has already talked to {npc.get('name', request.npc_id)} about this topic.
Return ONLY valid JSON."""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": API_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 400,
                "temperature": 0.7
            }
            resp = await client.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

            # Clean up JSON if wrapped in backticks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            result = json.loads(content)

            # Add hint if player has knowledge item
            hint_text = None
            if has_knowledge_item and "Dwarf Planet Archive" in request.player_items:
                hint_text = "💡 Archive Hint: ลองนึกถึงเกณฑ์ IAU 3 ข้อที่ COSMO-99 อธิบายไว้ใน Journal"

            return {
                "question": result.get("question", ""),
                "choices": result.get("choices", []),
                "correct_index": result.get("correct_index", 0),
                "explanation": result.get("explanation", ""),
                "difficulty": difficulty,
                "has_hint": hint_text is not None,
                "hint_text": hint_text
            }
    except json.JSONDecodeError as e:
        logger.error(f"Knowledge Check JSON parse error: {e}, content: {content[:200]}")
        # Return a fallback question
        return {
            "question": f"ข้อใดถูกต้องเกี่ยวกับ {topic}?",
            "choices": ["A. ข้อนี้ถูกต้อง", "B. ข้อนี้ไม่ถูกต้อง", "C. ข้อนี้อาจถูกหรือผิด", "D. ไม่มีข้อใดถูก"],
            "correct_index": 0,
            "explanation": "เกิดข้อผิดพลาดในการสร้างคำถาม — ข้อ A ถือว่าถูกต้องสำหรับรอบนี้",
            "difficulty": difficulty,
            "has_hint": False,
            "hint_text": None
        }
    except Exception as e:
        logger.error(f"Knowledge Check Generate Error: {e}")
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการสร้าง Knowledge Check")

@app.post("/api/knowledge-check/evaluate")
async def evaluate_knowledge_check(request: KnowledgeCheckEvaluateRequest):
    """
    ตรวจสอบคำตอบ Knowledge Check
    Returns: { pass, bonus_knowledge, shield_penalty, message }
    """
    is_correct = (request.selected_index == request.correct_index)

    if is_correct:
        return {
            "pass": True,
            "bonus_knowledge": 2,
            "shield_penalty": 0,
            "message": "✅ ถูกต้อง! ความรู้ที่ถูกต้องช่วยให้ภารกิจปลอดภัยขึ้น",
            "explanation": None
        }
    else:
        correct_choice = request.choices[request.correct_index] if request.correct_index < len(request.choices) else ""
        return {
            "pass": False,
            "bonus_knowledge": 0,
            "shield_penalty": 10,
            "message": f"❌ ไม่ถูกต้อง — เกราะลด 10% แต่ยังสามารถดำเนินภารกิจต่อได้",
            "explanation": request.explanation,
            "correct_answer": correct_choice
        }

@app.post("/api/npc/unlock-status")
async def check_npc_unlock(request: NPCUnlockCheckRequest):
    """
    ตรวจสอบว่า Chat History ครอบคลุม topic ที่จำเป็นสำหรับ unlock Mission
    ใช้ AI Evaluation (temperature ต่ำ) หรือ Keyword Matching
    """
    npc_id = request.npc_id
    unlock_config = NPC_UNLOCK_TOPICS.get(npc_id)

    if not unlock_config:
        return {"unlock_triggered": False, "topics_covered": [], "mission_unlocked": None}

    turn_count = len([m for m in request.chat_history if m.get("role") == "user"])
    min_turns = unlock_config.get("min_turns", 3)

    # Fast-fail: ยังสนทนาไม่ถึงเกณฑ์ขั้นต่ำ — ไม่เรียก LLM
    if turn_count < min_turns:
        return {
            "unlock_triggered": False,
            "missions_unlocked": [],
            "turn_count": turn_count,
            "min_turns_met": False,
            "feedback_for_student": f"สนทนาต่ออีก {min_turns - turn_count} ครั้ง เพื่อรวบรวมข้อมูลให้เพียงพอ"
        }

    # Determine which missions are chat-unlockable vs quest-locked
    missions_to_unlock = unlock_config.get("mission_unlocks", [])
    also_requires_quest = unlock_config.get("also_requires_quest")
    if also_requires_quest:
        chat_unlockable = [m for m in missions_to_unlock if not MISSIONS.get(m, {}).get("prerequisite_quest")]
        quest_locked = [m for m in missions_to_unlock if MISSIONS.get(m, {}).get("prerequisite_quest") == also_requires_quest]
    else:
        chat_unlockable = missions_to_unlock
        quest_locked = []

    # ถ้า Unlock ครบทุก Mission แล้ว — ไม่ต้องประเมินซ้ำ
    already_all_unlocked = all(m in request.current_unlocked for m in chat_unlockable)
    if already_all_unlocked:
        return {
            "unlock_triggered": False,
            "missions_unlocked": [],
            "quest_locked_missions": quest_locked,
            "turn_count": turn_count,
            "min_turns_met": True,
            "feedback_for_student": "ปลดล็อก Mission ทั้งหมดของ NPC นี้แล้ว"
        }

    # Fallback to keyword matching เมื่อไม่มี API Key
    if not API_KEY:
        user_text = " ".join([m.get("content", "") for m in request.chat_history if m.get("role") == "user"]).lower()
        keywords = unlock_config.get("topic_keywords", [])
        covered = [kw for kw in keywords if kw.lower() in user_text]
        passed = (len(covered) / max(len(keywords), 1)) >= 0.3
        newly_unlocked = [m for m in chat_unlockable if m not in request.current_unlocked] if passed else []
        return {
            "unlock_triggered": len(newly_unlocked) > 0,
            "missions_unlocked": newly_unlocked,
            "quest_locked_missions": quest_locked,
            "turn_count": turn_count,
            "min_turns_met": True,
            "feedback_for_student": "" if newly_unlocked else "ลองอธิบายหัวข้อที่เรียนรู้ให้ชัดเจนขึ้น"
        }

    # LLM Evaluation (On-Demand — เรียกเฉพาะเมื่อนักเรียนกดปุ่ม)
    required_topics = unlock_config.get("required_topics", [])
    npc_name = NPC_DATA.get(request.npc_id, {}).get("name", request.npc_id)
    chat_str = "\n".join([
        f"{'นักเรียน' if m['role'] == 'user' else npc_name}: {m.get('content', '')}"
        for m in request.chat_history
    ])

    eval_prompt = f"""You are an assessment system for the educational game "Helios Station".

NPC in conversation: {npc_name}
Topics the student must demonstrate understanding of: {', '.join(required_topics)}

Conversation:
{chat_str}

Evaluate whether the student (role: "นักเรียน" / Pilot) demonstrated sufficient understanding of the required topics.

Focus ONLY on what the STUDENT said — not what the NPC explained or hinted.

PASSING STANDARD — Quality over quantity:
- The student does NOT need to cover all {len(required_topics)} topic(s) — demonstrating the KEY IDEA of at least one is sufficient to pass.
- Accept paraphrasing, analogies, or informal language as long as the core concept is correct.
- Reserve failing ONLY for: (a) no relevant understanding shown, or (b) clearly incorrect scientific claims that were not corrected.

Respond with JSON only, no markdown:
{{"pass": true/false, "feedback_th": "คำอธิบาย 1-2 ประโยคเป็นภาษาไทย ระบุว่าผ่านเพราะอะไร หรือยังขาดความเข้าใจส่วนไหน"}}"""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": API_MODEL,
                "messages": [
                    {"role": "system", "content": "You are an educational assessment AI. Respond ONLY with valid JSON, no markdown."},
                    {"role": "user", "content": eval_prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.10
            }
            resp = await client.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content.strip())

            passed = result.get("pass", False)
            feedback = result.get("feedback_th", "")

            newly_unlocked = []
            if passed:
                newly_unlocked = [m for m in chat_unlockable if m not in request.current_unlocked]

            return {
                "unlock_triggered": len(newly_unlocked) > 0,
                "missions_unlocked": newly_unlocked,
                "quest_locked_missions": quest_locked,
                "turn_count": turn_count,
                "min_turns_met": True,
                "feedback_for_student": feedback,
                "message": f"✅ Unlock ภารกิจ: {', '.join(MISSIONS.get(m, {}).get('name', m) for m in newly_unlocked)}!" if newly_unlocked else feedback
            }
    except Exception as e:
        logger.error(f"NPC Unlock LLM Error: {e}")
        return {
            "unlock_triggered": False,
            "missions_unlocked": [],
            "turn_count": turn_count,
            "min_turns_met": True,
            "feedback_for_student": "เกิดข้อผิดพลาดในการประเมิน กรุณาลองใหม่อีกครั้ง"
        }

@app.post("/api/end-turn")
async def end_turn(request: TurnActionRequest):
    """
    ประมวลผล Mission Execution ทั้งหมดในรอบ
    Input: selected_missions[] with knowledge_check_passed status
    Output: Crystal gained, Shield changes, Event impact, Science narratives
    """
    state = request.game_state
    selected_missions = request.selected_missions
    items = state.stats.items or []

    # Knowledge Gate check
    current_round_index = state.round - 1
    if current_round_index < len(KNOWLEDGE_GATE):
        required_knowledge = KNOWLEDGE_GATE[current_round_index]
        if state.stats.knowledge < required_knowledge:
            raise HTTPException(
                status_code=400,
                detail=f"ข้อมูลวิจัยไม่เพียงพอ! ต้องการระดับ {required_knowledge} (ปัจจุบัน: {state.stats.knowledge}) — คุย NPC หรือทำ Quest เพื่อเพิ่มความรู้"
            )

    # Get current event
    scenario = next((s for s in SCENARIOS if s["id"] == state.scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=400, detail="Invalid scenario")
    event_id = scenario["schedule"][state.round - 1]
    event = next((e for e in EVENTS_MASTER if e["id"] == event_id), EVENTS_MASTER[0])
    crystal_multipliers = event.get("crystal_multiplier", {})
    event_shield_penalties = event.get("shield_penalty", {})

    # Knowledge Check Streak Bonus
    streak = state.knowledge_check_streak or 0
    streak_crystal_bonus = 1.10 if streak >= 3 else 1.0
    if streak >= 3:
        streak_message = f"🔥 Knowledge Streak x{streak}! Crystal +10% ทุก Mission รอบนี้"
    else:
        streak_message = None

    # Ripple Effect: Shield < 30% — HIGH mission energy cost +50%
    low_shield_warning = state.stats.shield < 30

    round_log = []
    item_effects = []
    total_crystals = 0
    total_shield_change = 0
    total_energy_cost = 0
    total_knowledge_gain = 0
    validation_errors = []
    journal_entries_new = []

    for sel in selected_missions:
        mission_id = sel.mission_id
        mission = MISSIONS.get(mission_id)
        if not mission:
            validation_errors.append(f"Mission ไม่พบ: {mission_id}")
            continue

        location_id = mission["location_id"]
        location = LOCATIONS.get(location_id, {})

        # Energy cost (with ripple effect)
        energy_cost = mission["energy_cost"]
        if mission["risk_level"] == "high" and low_shield_warning:
            energy_cost = int(energy_cost * 1.5)
            item_effects.append({"item": "Ripple Effect", "icon": "⚠️", "desc": f"เกราะต่ำกว่า 30% — {mission['name']} ใช้พลังงานเพิ่ม 50%"})

        if state.stats.energy < energy_cost:
            validation_errors.append(f"{mission['name']}: พลังงานไม่พอ (ต้องการ {energy_cost:,})")
            continue

        total_energy_cost += energy_cost

        # Crystal calculation
        base_crystal = mission.get("crystal_reward")
        if base_crystal is None:
            # Asteroid random
            if "cosmo" in (state.npc_briefings_done or []):
                base_crystal = random.randint(30, 80)  # Bonus from COSMO briefing
            else:
                base_crystal = random.randint(10, 40)

        # Apply event multiplier
        event_mult = crystal_multipliers.get(location_id, 1.0)

        # Heat Shield item: protect against Solar Flare penalty
        if event_id == 1 and "Heat Shield" in items and event_mult < 1.0 and location_id in [2, 3, 4]:
            item_effects.append({"item": "Heat Shield", "icon": "🛡️", "desc": f"ป้องกันความเสียหายจากพายุสุริยะที่ {location['name']}"})
            event_mult = max(event_mult, 0.8)  # Partial protection

        # Deflector Array: protect against Meteor Shower
        if event_id == 2 and "Deflector Array" in items and event_mult < 1.0:
            item_effects.append({"item": "Deflector Array", "icon": "🛰️", "desc": f"ปัดเป่าฝนอุกกาบาตที่ {location['name']}"})
            event_mult = max(event_mult, 0.9)

        # Deflector Array Mk.II: full meteor protection
        if event_id == 2 and "Deflector Array Mk.II" in items:
            item_effects.append({"item": "Deflector Array Mk.II", "icon": "🛡️🛡️", "desc": f"ป้องกันฝนอุกกาบาต 100% ที่ {location['name']}"})
            event_mult = max(event_mult, 1.0)

        # Spectral Analyzer: +30% crystal from rocky planets
        if "Spectral Analyzer" in items and location.get("type") in ["inner_planet", "habitable_zone", "mining"]:
            base_crystal = int(base_crystal * 1.30)
            item_effects.append({"item": "Spectral Analyzer", "icon": "🔬", "desc": f"Crystal +30% จาก {location['name']}"})

        # Knowledge Check bonus
        kc_passed = sel.knowledge_check_passed
        kc_bonus = 1.0
        kc_shield_penalty = 0
        if kc_passed is True:
            kc_bonus = 1.0
            total_knowledge_gain += 2
        elif kc_passed is False:
            kc_shield_penalty = 10

        final_crystals = int(base_crystal * event_mult * streak_crystal_bonus * kc_bonus)
        total_crystals += final_crystals

        # Shield change
        shield_cost = mission["shield_cost"]
        shield_heal = mission["shield_heal"]
        event_extra_shield = event_shield_penalties.get(location_id, 0)
        net_shield = shield_heal - shield_cost - event_extra_shield - kc_shield_penalty
        total_shield_change += net_shield

        # Science narrative for mission result
        science_narrative = _generate_science_narrative(mission_id, mission, event_id, kc_passed)

        round_log.append({
            "mission_id": mission_id,
            "location_id": location_id,
            "location_name": location.get("name", "Unknown"),
            "mission_name": mission["name"],
            "risk_level": mission["risk_level"],
            "energy_cost": energy_cost,
            "crystals_gained": final_crystals,
            "shield_change": net_shield,
            "event_multiplier": round(event_mult, 2),
            "knowledge_check_passed": kc_passed,
            "knowledge_bonus": 2 if kc_passed else 0,
            "science_narrative": science_narrative
        })

        # Auto Journal entry for mission
        journal_entries_new.append(JournalEntry(
            round=state.round,
            entry_type="mission_result",
            title=f"Mission: {mission['name']}",
            content=science_narrative,
            timestamp=datetime.now().strftime("%H:%M")
        ))

    # Calculate new stats
    new_energy = state.stats.energy - total_energy_cost
    new_crystals = state.stats.crystals + total_crystals
    new_shield = min(100, max(0, state.stats.shield + total_shield_change))
    new_knowledge = state.stats.knowledge + total_knowledge_gain

    # Emergency repair if shield critically low
    emergency_cost = 0
    if new_shield < 10:
        emergency_cost = int((10 - new_shield) * 500)
        new_energy -= emergency_cost
        new_shield = 10
        item_effects.append({"item": "Emergency Power", "icon": "⚠️", "desc": f"ดึงพลังงาน {emergency_cost:,} เพื่อรักษาเกราะฉุกเฉิน"})

    is_bankrupt = new_energy <= 0
    is_game_over = state.round >= state.max_rounds or is_bankrupt

    new_stats = {
        "energy": new_energy,
        "knowledge": new_knowledge,
        "crystals": new_crystals,
        "shield": new_shield,
        "items": state.stats.items
    }

    rank = calculate_rank(new_stats, state.completed_quests) if is_game_over else None

    # Ripple Effect warnings for next round
    ripple_warnings = []
    if new_shield < 30:
        ripple_warnings.append("⚠️ เกราะต่ำกว่า 30% — Mission HIGH จะใช้พลังงานเพิ่ม 50% รอบถัดไป")
    if new_knowledge < 20:
        ripple_warnings.append("⚠️ ความรู้ต่ำ — Crystal Reward บาง Mission จะแสดงเป็น '???' รอบถัดไป")
    if new_energy < 5000:
        ripple_warnings.append("⚠️ พลังงานวิกฤต — EXTREME Mission ทั้งหมดจะถูก Lock รอบถัดไป")

    return {
        "event": {"id": event_id, "title": event["title"], "narrative": event["narrative"]},
        "log": round_log,
        "item_effects": item_effects,
        "streak_message": streak_message,
        "total_crystals": total_crystals,
        "total_energy_cost": total_energy_cost,
        "total_shield_change": total_shield_change,
        "total_knowledge_gain": total_knowledge_gain,
        "emergency_cost": emergency_cost,
        "validation_errors": validation_errors,
        "new_stats": new_stats,
        "ripple_warnings": ripple_warnings,
        "is_game_over": is_game_over,
        "is_bankrupt": is_bankrupt,
        "rank": rank,
        "new_journal_entries": [e.dict() for e in journal_entries_new]
    }

def _generate_science_narrative(mission_id: str, mission: dict, event_id: int, kc_passed: Optional[bool]) -> str:
    """Generate science-based narrative for mission result"""
    narratives = {
        "mercury_high": "ดาวพุธไม่มีชั้นบรรยากาศปกป้อง ทำให้อุณหภูมิแกว่งระหว่าง +430°C และ -180°C ยานต้องใช้เกราะป้องกันความร้อนอย่างมีประสิทธิภาพ",
        "venus_high": "ชั้น CO₂ 96.5% ของดาวศุกร์ทำให้เกิด Greenhouse Effect รุนแรง อุณหภูมิ 465°C และความดัน 90 atm ท้าทายระบบป้องกันของยานอย่างมาก",
        "venus_extreme": "บรรยากาศชั้นล่างของดาวศุกร์มีฝนกรดซัลฟิวริก H₂SO₄ ความดันเทียบเท่าใต้มหาสมุทรลึก 900 เมตร ต้องมีอุปกรณ์พิเศษ",
        "mars_high": "ดาวอังคารอยู่ที่ขอบ Habitable Zone ชั้นบรรยากาศบาง (CO₂ 95%) ให้การป้องกันน้อย แต่การขุดใต้ดินพบร่องรอยน้ำในอดีต",
        "mars_extreme": "น้ำแข็งขั้วโลกดาวอังคารประกอบด้วย CO₂ แข็งและ H₂O น้ำแข็งซ้อนกัน การขุดเจาะค้นพบหลักฐานสภาพอากาศโบราณ",
        "jupiter_high": "เขตรังสีแวน อัลเลนของดาวพฤหัสประกอบด้วยโปรตอนและอิเล็กตรอนพลังงานสูง สนามแม่เหล็กดาวพฤหัสแรงกว่าโลก 20,000 เท่า",
        "jupiter_extreme": "ไฮโดรเจนในดาวพฤหัสเปลี่ยนเป็นสถานะโลหะเหลวที่ความดันสูง — แหล่ง Metallic Crystal อันทรงคุณค่า",
        "saturn_high": "วงแหวนดาวเสาร์กว้าง 282,000 กม. แต่หนาเพียง 10-100 เมตร ประกอบด้วยน้ำแข็ง 90-95% สะท้อนแสงอาทิตย์สดใส",
        "neptune_high": "พายุ Great Dark Spot ของดาวเนปจูนเกิดจากความร้อนภายในที่ผลิตพลังงานมากกว่าดวงอาทิตย์ให้ 2.6 เท่า ไม่ใช่จากความร้อนของดวงอาทิตย์"
    }

    base = narratives.get(mission_id, f"Mission {mission['name']} ดำเนินการสำเร็จ")

    if kc_passed is True:
        return f"✅ {base} — ความรู้ที่ถูกต้องช่วยให้ภารกิจปลอดภัยและมีประสิทธิภาพสูงขึ้น"
    elif kc_passed is False:
        return f"⚠️ {base} — การขาดความรู้ทำให้เกราะยานได้รับความเสียหายเพิ่มเติม 10%"
    else:
        return base

@app.post("/api/chat")
async def chat_with_npc(request: ChatRequest):
    """SSE Streaming Chat กับ NPC — Phase-Aware behavior"""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API Key missing")

    npc = NPC_DATA.get(request.npc_id)
    if not npc:
        raise HTTPException(status_code=400, detail="Invalid NPC")

    messages = [{"role": "system", "content": npc["system"]}]

    # Phase-aware context injection
    phase = request.current_phase
    phase_context = ""
    if phase == "recon":
        phase_context = "CURRENT PHASE: RECONNAISSANCE — ผู้เล่นกำลังขอข้อมูลก่อนออก Mission ให้ข้อมูลที่เป็นประโยชน์และกระตุ้นให้ถามเรื่อง Mission-relevant topics"
    elif phase in ["quest_explore", "quest_apply"]:
        phase_context = "CURRENT PHASE: QUEST LEARNING — ใช้ Socratic Method อย่าบอกคำตอบตรงๆ ให้ Hints ทีละขั้น"
    elif phase == "quest_reflect":
        phase_context = "CURRENT PHASE: QUEST REFLECTION — สรุปสิ่งที่ผู้เล่นเรียนรู้ ให้กำลังใจ"

    if phase_context:
        messages.append({"role": "system", "content": phase_context})

    # Quest mode injection
    if request.active_quest:
        quest = QUESTS.get(request.active_quest)
        if quest and quest["npc_id"] == request.npc_id:
            quest_phase = "explore"  # Default
            if "apply" in phase:
                quest_phase = "apply"
            elif "reflect" in phase:
                quest_phase = "reflect"
            elif "hook" in phase:
                quest_phase = "hook"

            phase_prompt = quest.get("phase_prompts", {}).get(quest_phase, "")
            messages.append({"role": "system", "content": f"QUEST MODE — {quest['archetype'].upper()}: {quest['teacher_prompt']}"})
            if phase_prompt:
                messages.append({"role": "system", "content": f"CURRENT QUEST PHASE GUIDANCE: {phase_prompt}"})

    # Resolve any remaining raw IDs to human-readable names before sending to LLM
    resolved_context = request.game_context
    if request.active_quest:
        quest_name = QUESTS.get(request.active_quest, {}).get("name", "")
        if quest_name:
            resolved_context = resolved_context.replace(
                f"Quest:{request.active_quest}", f"Quest:{quest_name}"
            )
    messages.append({"role": "system", "content": f"GAME CONTEXT:\n{resolved_context}\n\nRespond in character. Keep response concise (max 3 paragraphs)."})

    for msg in request.history[-12:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": request.user_message})

    async def generate_stream():
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
                is_quest_mode = bool(request.active_quest and QUESTS.get(request.active_quest, {}).get("npc_id") == request.npc_id)

                payload = {
                    "model": API_MODEL,
                    "messages": messages,
                    "stream": True,
                    "max_tokens": 800,
                    "temperature": 0.60 if is_quest_mode else 0.75
                }

                async with client.stream("POST", f"{API_BASE_URL}/chat/completions", headers=headers, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data:
                                    content = data["choices"][0].get("delta", {}).get("content", "")
                                    if content:
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                            except:
                                continue
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"Chat Error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.post("/api/quest/accept")
async def quest_accept(request: QuestRequest):
    """รับ Quest — ตรวจสอบ unlock condition และ entry cost"""
    state = request.game_state
    quest = QUESTS.get(request.quest_id)
    if not quest:
        raise HTTPException(status_code=400, detail="Invalid quest ID")
    if state.active_quest:
        raise HTTPException(status_code=400, detail="มีภารกิจที่กำลังทำอยู่แล้ว")
    if request.quest_id in state.completed_quests:
        raise HTTPException(status_code=400, detail="ภารกิจนี้สำเร็จแล้ว")

    # Check unlock conditions
    unlock_condition = quest.get("unlock_condition", "start")
    completed = state.completed_quests or []

    unlock_ok = True
    unlock_msg = ""

    if unlock_condition == "start":
        unlock_ok = True
    elif unlock_condition == "execute_venus_once":
        # Check if any Venus mission has been executed
        executed = state.executed_missions_this_round or []
        history = state.history or []
        venus_executed = any("venus" in str(h) for h in history)
        if not venus_executed:
            unlock_ok = False
            unlock_msg = "ต้อง Execute Mission ที่ดาวศุกร์อย่างน้อย 1 ครั้งก่อน"
    elif "_and_" in unlock_condition:
        # e.g., "q6_investigation_and_q7_rival"
        req_quests = unlock_condition.split("_and_")
        missing = [q for q in req_quests if q not in completed]
        if missing:
            unlock_ok = False
            missing_names = [QUESTS.get(q, {}).get("name", q) for q in missing]
            unlock_msg = f"ต้องผ่าน Quest ก่อน: {', '.join(missing_names)}"
    elif unlock_condition in QUESTS:
        if unlock_condition not in completed:
            unlock_ok = False
            req_quest_name = QUESTS.get(unlock_condition, {}).get("name", unlock_condition)
            unlock_msg = f"ต้องผ่าน Quest '{req_quest_name}' ก่อน"

    if not unlock_ok:
        raise HTTPException(status_code=400, detail=unlock_msg)

    # Entry energy cost
    if state.stats.energy < 1000:
        raise HTTPException(status_code=400, detail="พลังงานไม่พอสำหรับการเริ่มภารกิจ (1,000 ยูนิต)")

    new_energy = state.stats.energy - 1000
    npc_name = NPC_DATA.get(quest["npc_id"], {}).get("name", quest["npc_id"])

    # Initialize fragment tracking for Q6 Investigation
    quest_fragments = {}
    if quest.get("archetype") == "investigation":
        for npc_id in quest.get("investigation_npcs", []):
            quest_fragments[npc_id] = False

    return {
        "success": True,
        "quest": quest,
        "new_energy": new_energy,
        "active_quest": quest["id"],
        "quest_turn_count": 0,
        "quest_phase": "hook",
        "quest_fragments": quest_fragments,
        "message": f"รับภารกิจ '{quest['name']}' สำเร็จ! ใช้พลังงาน 1,000 ยูนิต ติดต่อ {npc_name} เพื่อดำเนินการ"
    }

@app.post("/api/quest/evaluate")
async def quest_evaluate(request: QuestEvaluateRequest):
    """AI ประเมิน Quest Chat History"""
    if not API_KEY:
        return {"pass": False, "score": 0, "feedback": "ไม่สามารถประเมินได้ (ไม่มี API Key)"}

    quest = QUESTS.get(request.quest_id)
    if not quest:
        raise HTTPException(status_code=400, detail="Invalid quest ID")

    chat_str = "\n".join([f"{'AI' if msg['role'] == 'assistant' else 'Pilot'}: {msg['content']}" for msg in request.chat_history])

    # Special handling for Q5 Dilemma
    dilemma_note = ""
    if quest.get("archetype") == "dilemma":
        choice = request.dilemma_choice or "unknown"
        dilemma_note = f"\nPlayer's choice: {choice}"
        if choice == "confirm_pluto":
            return {
                "pass": False,
                "score": 1,
                "feedback": "คุณยืนยันว่าพลูโตเป็นดาวเคราะห์หลัก — ข้อมูลนี้ไม่ถูกต้อง COSMO-99 ยังคงใช้ฐานข้อมูลเก่า ความรู้ไม่เพิ่มขึ้น",
                "dilemma_consequence": "wrong_choice"
            }

    eval_prompt = f"""You are a science teacher evaluating a Thai middle school student in the game "Helios Station".

Quest: {quest['name']}
Archetype: {quest['archetype']}
Topic: {quest['topic']}
Bloom's Level: {quest['bloom_level']}
Evaluation Criteria: {quest['evaluation_criteria']}
{dilemma_note}

Conversation:
{chat_str}

Evaluate if the student (Pilot) demonstrated sufficient understanding based on the criteria.

Context: This is a Socratic learning conversation. The AI/NPC guided with hints step-by-step, not direct answers.
Focus ONLY on what the PILOT said — not the AI's explanations or hints.

PASSING STANDARD — Quality over quantity:
- A student who explains the core concept correctly in 2 turns PASSES before a student who talks for 5 turns without demonstrating understanding.
- The student does NOT need to cover every detail in the criteria — demonstrating the KEY IDEA is sufficient to pass.
- Accept paraphrasing, analogies, or informal language as long as the core concept is correct.
- Reserve a failing score ONLY for: (a) no relevant understanding shown, or (b) clearly incorrect scientific claims that were not corrected.

SCORING GUIDE:
- Score 5: Core concept + supporting details, explained clearly in own words
- Score 4: Core concept clearly demonstrated, minor details missing
- Score 3: Core concept partially demonstrated, some confusion but correct direction
- Score 2: Attempted but mostly incorrect or incomplete — still shows effort
- Score 1: No relevant understanding or clearly wrong answer

Respond with JSON only, no markdown:
{{"pass": true/false, "score": 1-5, "feedback": "คำอธิบาย 2-3 ประโยคเป็นภาษาไทย ระบุว่าผ่านเพราะอะไร หรือยังขาดความเข้าใจส่วนไหน"}}"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": API_MODEL,
                "messages": [
                    {"role": "system", "content": "You are an educational assessment AI. Respond ONLY with valid JSON."},
                    {"role": "user", "content": eval_prompt}
                ],
                "max_tokens": 300,
                "temperature": 0.20
            }
            resp = await client.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload)
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())
            eval_pass = result.get("pass", False)
            eval_score = result.get("score", 0)
            eval_feedback = result.get("feedback", "ไม่สามารถประเมินได้")

            # Piggyback Mission Unlock: ถ้า Quest ผ่าน → ปลดล็อก Mission ที่ผูกกับ NPC นี้โดยอัตโนมัติ
            missions_unlocked_by_quest = []
            if eval_pass:
                quest_npc_id = quest.get("npc_id")
                npc_unlock = NPC_UNLOCK_TOPICS.get(quest_npc_id, {})
                if npc_unlock:
                    for mission_id in npc_unlock.get("mission_unlocks", []):
                        mission = MISSIONS.get(mission_id, {})
                        prereq_quest = mission.get("prerequisite_quest")
                        # ถ้า mission ต้องการ prerequisite_quest → ตรวจว่าตรงกับ quest ที่กำลัง complete อยู่
                        if prereq_quest and prereq_quest != request.quest_id:
                            continue
                        missions_unlocked_by_quest.append(mission_id)

            return {
                "pass": eval_pass,
                "score": eval_score,
                "feedback": eval_feedback,
                "missions_unlocked": missions_unlocked_by_quest
            }
    except Exception as e:
        logger.error(f"Quest Evaluation Error: {e}")
        return {"pass": False, "score": 0, "feedback": "เกิดข้อผิดพลาดในการประเมิน"}

@app.post("/api/quest/complete")
async def quest_complete(request: QuestRequest):
    """บันทึก Quest สำเร็จ — ให้ Rewards"""
    state = request.game_state
    quest = QUESTS.get(request.quest_id)
    if not quest:
        raise HTTPException(status_code=400, detail="Invalid quest ID")

    rewards = quest["rewards"]

    new_stats = {
        "energy": state.stats.energy + rewards.get("energy", 0),
        "knowledge": state.stats.knowledge + rewards.get("knowledge", 0),
        "crystals": state.stats.crystals + rewards.get("crystals", 0),
        "shield": min(100, state.stats.shield + rewards.get("shield_heal", 0)),
        "items": list(state.stats.items)
    }

    if rewards.get("item") and rewards["item"] not in new_stats["items"]:
        new_stats["items"].append(rewards["item"])

    new_completed = list(state.completed_quests)
    if quest["id"] not in new_completed:
        new_completed.append(quest["id"])

    # unlocked_missions ถูกอัปเดตแล้วจาก /api/quest/evaluate ก่อนหน้า
    # ส่ง state.unlocked_missions กลับไปตามที่ Frontend อัปเดตมา
    newly_unlocked = list(state.unlocked_missions or [])

    # Auto Journal entry
    journal_entry = JournalEntry(
        round=state.round,
        entry_type="quest_complete",
        title=f"Quest สำเร็จ: {quest['name']}",
        content=f"{NPC_DATA.get(quest['npc_id'], {}).get('name', 'NPC')} บทเรียน: {quest['topic']} — {rewards.get('knowledge', 0)} Knowledge, {rewards.get('crystals', 0)} Crystal",
        timestamp=datetime.now().strftime("%H:%M")
    )

    return {
        "success": True,
        "quest_name": quest["name"],
        "archetype": quest["archetype"],
        "rewards": rewards,
        "new_stats": new_stats,
        "completed_quests": new_completed,
        "unlocked_missions": newly_unlocked,
        "active_quest": None,
        "quest_phase": "hook",
        "achievement": quest.get("achievement"),
        "journal_entry": journal_entry.dict(),
        "message": f"ภารกิจ '{quest['name']}' สำเร็จ! ได้รับ {rewards.get('knowledge', 0)} Knowledge"
    }

@app.post("/api/quest/update-fragment")
async def update_quest_fragment(request: dict):
    """อัปเดต Fragment สำหรับ Q6 Investigation Quest"""
    quest_id = request.get("quest_id")
    npc_id = request.get("npc_id")
    fragments = request.get("current_fragments", {})

    if quest_id != "q6_investigation":
        return {"success": False, "message": "Not an investigation quest"}

    quest = QUESTS.get(quest_id)
    investigation_npcs = quest.get("investigation_npcs", [])

    fragments[npc_id] = True
    fragments_collected = sum(1 for v in fragments.values() if v)
    total_fragments = len(investigation_npcs)

    return {
        "success": True,
        "fragments": fragments,
        "fragments_collected": fragments_collected,
        "total_fragments": total_fragments,
        "all_collected": fragments_collected >= total_fragments,
        "message": f"เก็บข้อมูลจาก {NPC_DATA.get(npc_id, {}).get('name', npc_id)} สำเร็จ ({fragments_collected}/{total_fragments})"
    }

@app.post("/api/journal/add-entry")
async def add_journal_entry(request: JournalAddRequest):
    """เพิ่ม Entry ใน Learning Journal"""
    state = request.game_state
    entry = request.entry
    if not entry.timestamp:
        entry.timestamp = datetime.now().strftime("%H:%M")

    current_entries = list(state.journal_entries or [])
    current_entries.append(entry)

    return {
        "success": True,
        "entry": entry.dict(),
        "total_entries": len(current_entries)
    }

@app.post("/api/journal/get")
async def get_journal(request: GameState):
    """ดึง Journal ทั้งหมดของ session"""
    entries = request.journal_entries or []
    return {
        "entries": [e.dict() for e in entries],
        "total": len(entries),
        "summary": {
            "total_knowledge": request.stats.knowledge,
            "total_crystals": request.stats.crystals,
            "quests_completed": len(request.completed_quests)
        }
    }

@app.post("/api/generate-insights")
async def generate_insights(request: InsightsRequest):
    """สร้าง End-Game Debrief Report จาก Commander TERRA"""
    if not API_KEY:
        return {"insights": "AI Insights unavailable.", "success": False}

    state = request.game_state
    quest_names = [QUESTS.get(q, {}).get("name", q) for q in state.completed_quests]

    summary = f"บันทึกสุดท้ายของสถานี Helios\n"
    summary += f"Scenario: {state.scenario_id}, รอบที่ผ่าน: {state.round}\n"
    summary += f"Energy: {state.stats.energy:,}, Crystal: {state.stats.crystals}, Knowledge: {state.stats.knowledge}, Shield: {state.stats.shield}%\n"
    summary += f"Quest สำเร็จ ({len(state.completed_quests)}/8): {', '.join(quest_names) if quest_names else 'ไม่มี'}\n"
    summary += f"Items: {', '.join(state.stats.items) if state.stats.items else 'ไม่มี'}\n"
    rank = calculate_rank(state.stats.dict(), state.completed_quests)
    summary += f"Rank: {rank['name']}\n"

    system_prompt = """You are "Commander TERRA" debriefing a pilot after a Helios Station mission simulation.
Analyze their performance across Energy, Crystal, Knowledge, Quests completed, and Science understanding.
Write in formal, sci-fi Thai with a concluding tone. Use bullet points and bold text.
Reference specific science concepts they learned (or missed) based on Quest completion.
Provide their Rank assessment and 2-3 specific improvement tips for next mission.
Keep the response under 400 words."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": API_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": summary}
                ],
                "max_tokens": 700,
                "temperature": 0.60
            }
            resp = await client.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload)
            content = resp.json()["choices"][0]["message"]["content"]
            return {"insights": content, "success": True, "rank": rank}
    except Exception as e:
        logger.error(f"Insights Error: {e}")
        return {"insights": "เกิดข้อผิดพลาดในการประมวลผลรายงาน", "success": False, "rank": rank}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)