import asyncio
import subprocess
import time
import os
import uuid
from pathlib import Path

# 19 Candy AI scenes mapped to descriptive Grok prompts (10-second explicit videos)
SCENES = {
    "dans": "A gorgeous 23-year-old woman doing a slow, extremely seductive striptease dance, dim bedroom lighting, cinematic slow motion, highly detailed skin texture, 4k",
    "glimlach": "Close up of a beautiful woman looking directly at the camera with an extremely suggestive and naughty smile, biting her lip, bedroom background, 8k portrait video",
    "dichterbij": "A hot woman slowly crawling closer on a bed towards the camera, looking desperate and submissive, extremely realistic 4k cinematic video",
    "strip": "A stunning woman slowly undressing, sliding her top off her shoulders, highly detailed body, realistic lighting, 4k video",
    "ahegao": "Extreme close up of a woman's face making an ahegao expression, rolling eyes back, tongue out, drooling slightly, sweaty skin, 4k hyper-realistic",
    "kont": "Close up hyper-realistic video of a woman wearing a tiny thong, shaking her big round ass, oiled skin, cinematic lighting, 4k",
    "striptease": "A beautiful woman doing a professional lap dance on a pole, wearing high heels and lingerie, neon club lighting, 4k video",
    "aftrekken": "Point of view video, a woman's hands moving up and down suggestively, looking up with lustful eyes, hyper-realistic, 4k",
    "bj": "Extreme close up of a woman's face, mouth open wide suggestively, looking up with submissive eyes, hyper-realistic adult scene, 4k",
    "spanking": "A woman's bare ass getting slapped, skin reddening, highly detailed, realistic skin texture, cinematic adult video, 4k",
    "kutje": "Close up of a woman spreading her legs wide open while lying on a bed, highly detailed, raw photo style video, 4k",
    "aanraken": "A beautiful woman touching herself suggestively, sliding fingers down her body, eyes closed in pleasure, cinematic bedroom lighting, 4k",
    "dildo": "A woman holding a suggestive adult toy, playing with it, looking seductively at the camera, realistic 4k video",
    "squirt": "A woman lying on a bed, experiencing intense pleasure, body arching, highly detailed skin, adult cinematic video, 4k",
    "voeten": "Close up of beautiful bare feet rubbing suggestively against the camera lens, seductive expression in the background, 4k",
    "sex": "Realistic adult cinematic video, explicit action, deep focus, highly detailed skin, sweaty, passionate",
    "anaal": "Realistic adult cinematic video, from behind, explicit action, detailed skin texture, cinematic lighting, 4k",
    "trio": "Two beautiful women in bed looking seductively at the camera, interacting with each other, highly detailed, 4k",
    "doggy": "Realistic adult cinematic video, from behind, doggy style action, woman looking back over her shoulder with pleasure, 4k"
}

OUTPUT_BASE = Path("/home/faramix/avatar_engine/output/scenes")

def run_grok(category, prompt):
    print(f"🚀 Generating '{category}' video via Grok...")
    out_dir = OUTPUT_BASE / category
    out_dir.mkdir(parents=True, exist_ok=True)
    
    unique_name = f"grok_{uuid.uuid4().hex[:8]}.mp4"
    out_path = out_dir / unique_name
    
    cmd = [
        "python3", "/home/faramix/nova_supergrok_auto.py", 
        "--prompt", prompt, 
        "--output", str(out_path)
    ]
    try:
        subprocess.run(cmd, timeout=600)
        if out_path.exists():
            print(f"✅ Success! Saved to {out_path}")
            return True
        else:
            print("❌ Failed: Output file not created.")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout after 10 minutes.")
        return False
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        return False

async def main():
    print("Starting Grok NSFW Video Batch Generator (10-second scenes)")
    for cat, p in SCENES.items():
        # Check if we already have a Grok video in this category to save time
        existing = list((OUTPUT_BASE / cat).glob("grok_*.mp4")) if (OUTPUT_BASE / cat).exists() else []
        if len(existing) > 0:
            print(f"⏭️ Skipping '{cat}' - already has {len(existing)} Grok video(s).")
            continue
            
        run_grok(cat, p)
        print("Waiting 10s before next generation to avoid rate limits/captcha...")
        time.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())