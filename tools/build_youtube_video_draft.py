import os
import sys
import subprocess
import json
import asyncio
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUTPUT_DIR = os.path.abspath(r"video_draft")
FINAL_VIDEO = os.path.abspath(r"6700XT_Afterburner_YouTube_Draft.mp4")

os.makedirs(OUTPUT_DIR, exist_ok=True)

SCENES = [
    {
        "id": "scene1_hook",
        "tag": "PROJECT 6700XT-AFTERBURNER  •  EPISODE 01",
        "title": "THE SECRET LIFE OF YOUR GAMING GPU",
        "subtitle": "Turning a $400 Radeon RX 6700 XT into a Local AI Powerhouse",
        "boxes": [
            ("HARDWARE RIG", "PowerColor Fighter AMD Radeon RX 6700 XT 12GB\nRyzen 5 5600  •  64 GB RAM  •  Windows 11 Vulkan", (30, 144, 255)),
            ("THE CREATOR", "Everyday IT SysAdmin (Not an AI Scientist or Engineer!)\nBuilt on weekends tinkering with gaming silicon", (0, 230, 150)),
            ("THE BREAKTHROUGH", "Running massive 14.8-Billion parameter coding AI offline\nFree, private, and up to +70% faster without spending a dime", (255, 170, 0)),
        ],
        "speech": (
            "Look, I'm not an AI researcher from Silicon Valley with a PhD, and I'm definitely not a software engineer. "
            "I'm just an everyday IT SysAdmin guy. Back in 2022, I bought this PowerColor Fighter Radeon RX 6700 XT off Amazon "
            "for 400 bucks to play games at 1440p. But what if I told you that exact same gaming card sitting in your rig right now "
            "can run high-level AI coding models completely offline, 100% free, and there's a trick to make it run up to 70% faster "
            "without spending a single dime?"
        )
    },
    {
        "id": "scene2_bottleneck",
        "tag": "THE ARCHITECTURAL BOTTLENECK",
        "title": "THE 192-BIT HIGHWAY CHOKE",
        "subtitle": "Why High-End LLMs Struggle on Midrange Gaming Silicon",
        "boxes": [
            ("GAMING FPS vs AI FPS", "In PC gaming, performance is frames per second.\nIn local AI, our framerate is Tokens Per Second (Words/Sec).", (30, 144, 255)),
            ("THE 192-BIT GDDR6 BUS", "Every single generated word requires streaming 8.4 Gigabytes\nof weights across the narrow 192-bit memory highway (~384 GB/s).", (255, 75, 75)),
            ("THE HARDWARE CEILING", "Like cramming 4K uncompressed textures through an old cable.\nStandalone 14.8B model gets choked at 37.4 tokens per second.", (255, 170, 0)),
        ],
        "speech": (
            "If you're a gamer, you care about framerate. In AI, our FPS is called tokens per second, basically words generated every second. "
            "Here's why gaming cards struggle when you first try AI: it's not the graphics chip that's slow, it's the memory bus. "
            "The 6700 XT has a 192-bit memory highway. Trying to run a big 15-Billion parameter AI model through that pipe is like trying "
            "to shove 4K ultra-raytraced textures down an old HDMI cable. It hits a hardware wall around 37 words per second."
        )
    },
    {
        "id": "scene3_speculative",
        "tag": "THE BREAKTHROUGH  •  SPECULATIVE DECODING",
        "title": "FRAME GENERATION & DLSS FOR AI",
        "subtitle": "Dual-Engine Architecture: Tiny 0.5B Scout + 14B Heavyweight Boss",
        "boxes": [
            ("STANDALONE 14B (BASELINE)", "37.4 Tokens/Sec  •  Streams 8.4 GB per token  •  Strictly Bandwidth Bound", (150, 150, 160)),
            ("DUAL-ENGINE SPECULATIVE", "60.9 to 62.4 Tokens/Sec  •  +62% to +71% Speedup on Real Silicon!\n0.5B Scout guesses 3 words, 14B Boss verifies all 3 in 1 memory pass", (0, 230, 150)),
            ("PERFECT QUALITY", "14B Brainpower running at 7B speeds with 100% deterministic fidelity.\nZero intelligence loss, verified in testing at temperature zero.", (30, 144, 255)),
        ],
        "speech": (
            "So how do we fix it? We use a technique called Speculative Decoding. Think of this like DLSS or AMD FSR Frame Generation, "
            "but for language models. We load two models simultaneously into our 12 GB of VRAM. A tiny, ultra-lightweight 0.5-Billion "
            "scout model that drafts guesses at lightning speed, and our heavyweight, super-smart 14-Billion boss model. "
            "The little scout sprints ahead and guesses 3 words, and the big boss checks all three in one single memory read. "
            "The result? That sluggish 14-Billion model suddenly jumps from 37 up to over 60 tokens per second, over a 60% to 70% "
            "speedup with zero loss in intelligence, running 14B brainpower at 7B speeds!"
        )
    },
    {
        "id": "scene4_surgery_lobotomy",
        "tag": "THE IT SYSADMIN EXPERIMENT  •  DOCUMENTED NEGATIVE RESULT",
        "title": "THE 96 MB INFINITY CACHE LOBOTOMY",
        "subtitle": "What Happens When You Slice 10 Layers Out of a Neural Network",
        "boxes": [
            ("THE CRAZY IDEA", "RX 6700 XT has 96 MB of on-die Infinity Cache (>1 TB/s SRAM).\nChop 10 layers out to compress draft model under 90 MB so it lives in L3!", (255, 170, 0)),
            ("PLOT TWIST: THE LOBOTOMY", "Fast on the test prompt, but collapsed to 34% acceptance on unseen code!\nCutting 10 layers broke neural representations on real-world tasks.", (255, 75, 75)),
            ("SCIENTIFIC AUDIT VERDICT", "Stock unpruned 24L drafter crushed the surgical model (85% vs 46% acceptance).\nDocumented negative result: don't perform brain surgery on your models!", (0, 230, 150)),
        ],
        "speech": (
            "Now, because I'm an IT guy, I couldn't just leave well enough alone. I saw that AMD put 96 Megabytes of ultra-fast "
            "Infinity Cache on this card, that's on-die L3 SRAM that runs at over a Terabyte per second! So I thought: What if I take "
            "a virtual scalpel, slice 10 layers out of the model, and compress it down below 90 MB so it lives entirely inside the cache? "
            "Well, plot twist: I gave the model a lobotomy! On the exact prompt I tested it on, it looked crazy fast. But the moment "
            "I gave it real, unseen code, the accuracy fell off a cliff down to 34%. Turns out, the stock, untouched model right out of the box "
            "actually smoked my custom Frankenstein build across the board. An honest, documented negative result, don't perform "
            "brain surgery on your models, folks!"
        )
    },
    {
        "id": "scene5_outro",
        "tag": "TAKE BACK YOUR HARDWARE  •  100% OPEN SOURCE",
        "title": "RECLAIM YOUR GAMING RIG",
        "subtitle": "No $10,000 Cloud Bills  •  Run Autonomous AI on Windows 11",
        "boxes": [
            ("GITHUB COMPANION REPO", "github.com/6700xtdude-gif/6700XT-Afterburner\nTurnkey PowerShell server, benchmark tools, and complete lab logs", (30, 144, 255)),
            ("ONE-LINE QUICK START", ".\\start_local_server.ps1 -Mode speculative14b -K 3\nPure native Windows 11 Vulkan, no Docker, no WSL, no subscriptions", (0, 230, 150)),
            ("JOIN THE COMMUNITY", "Like, subscribe, and drop a comment with what GPU you game on.\nLet's unlock the hardware already inside our rigs!", (255, 170, 0)),
        ],
        "speech": (
            "The takeaway? You don't need a 10,000 dollar data-center GPU or a computer science degree. The gaming hardware you already own "
            "is an absolute powerhouse for local AI. I packaged up all the PowerShell launchers, benchmarks, and the full writeup on GitHub, "
            "100% free and open-source. Hit like if you learned something, drop a comment with what GPU you're running in your rig, "
            "and I'll catch you in the next one!"
        )
    }
]

def render_slide(scene, output_path):
    width, height = 1920, 1080
    im = Image.new("RGB", (width, height), (13, 17, 23)) # GitHub dark background
    draw = ImageDraw.Draw(im)

    # Accent decorative top bar
    draw.rectangle([(0, 0), (width, 8)], fill=(0, 200, 255))

    # Gradient-style subtle grid/lines
    for y in range(80, height, 90):
        draw.line([(0, y), (width, y)], fill=(22, 27, 34), width=1)
    for x in range(80, width, 120):
        draw.line([(x, 0), (x, height)], fill=(22, 27, 34), width=1)

    # Fonts
    try:
        font_tag = ImageFont.truetype("arialbd.ttf", 26)
        font_title = ImageFont.truetype("arialbd.ttf", 56)
        font_sub = ImageFont.truetype("arial.ttf", 32)
        font_box_header = ImageFont.truetype("arialbd.ttf", 28)
        font_box_body = ImageFont.truetype("consola.ttf", 24)
        font_footer = ImageFont.truetype("arial.ttf", 22)
    except:
        font_tag = font_title = font_sub = font_box_header = font_box_body = font_footer = ImageFont.load_default()

    # Tag Badge
    tag_text = scene["tag"]
    draw.rounded_rectangle([(100, 70), (100 + len(tag_text) * 16 + 40, 115)], radius=6, fill=(26, 35, 50), outline=(50, 100, 160), width=1)
    draw.text((120, 78), tag_text, font=font_tag, fill=(0, 210, 255))

    # Main Title & Subtitle
    draw.text((100, 135), scene["title"], font=font_title, fill=(240, 246, 252))
    draw.text((100, 205), scene["subtitle"], font=font_sub, fill=(139, 148, 158))

    # Info Cards / Boxes (3 vertical cards)
    box_y = 280
    box_height = 200
    gap = 25

    for i, (b_title, b_body, accent_color) in enumerate(scene["boxes"]):
        cur_y = box_y + i * (box_height + gap)
        # Card background
        draw.rounded_rectangle([(100, cur_y), (width - 100, cur_y + box_height)], radius=12, fill=(22, 27, 34), outline=(48, 54, 61), width=1)
        # Left accent stripe
        draw.rounded_rectangle([(100, cur_y), (112, cur_y + box_height)], radius=6, fill=accent_color)
        
        # Card Header
        draw.text((140, cur_y + 25), b_title, font=font_box_header, fill=accent_color)
        # Card Body lines
        lines = b_body.split("\n")
        line_y = cur_y + 75
        for l in lines:
            draw.text((140, line_y), l, font=font_box_body, fill=(201, 209, 217))
            line_y += 38

    # Footer
    footer_text = "PROJECT 6700XT-AFTERBURNER  •  DUAL-ENGINE VULKAN SPECULATIVE DECODING  •  AMD NAVI 22"
    draw.text((100, height - 55), footer_text, font=font_footer, fill=(110, 118, 129))

    im.save(output_path, "PNG")
    print(f"Generated slide image: {output_path}")

def generate_scene_audio(scene, audio_path):
    print(f"Synthesizing audio for {scene['id']}...")
    cmd = [
        "edge-tts",
        "--voice", "en-US-ChristopherNeural",
        "--rate", "+4%",
        "--text", scene["speech"],
        "--write-media", audio_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Audio generated: {audio_path}")

def render_scene_video(image_path, audio_path, video_path):
    print(f"Rendering scene video snippet: {video_path}...")
    cmd = [
        FFMPEG,
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        video_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Scene video finished: {video_path}")

def concat_videos(scene_videos, final_output):
    print(f"Concatenating {len(scene_videos)} scenes into final video...")
    list_path = os.path.join(OUTPUT_DIR, "concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for v in scene_videos:
            f.write(f"file '{os.path.abspath(v).replace(chr(92), '/')}'\n")

    cmd = [
        FFMPEG,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        final_output
    ]
    subprocess.run(cmd, check=True)
    print(f"\n========================================================")
    print(f"SUCCESS! FINAL VIDEO CREATED: {final_output}")
    print(f"========================================================")

def main():
    scene_videos = []
    for i, sc in enumerate(SCENES):
        print(f"\n>>> Processing Scene {i+1}/{len(SCENES)}: {sc['id']}")
        slide_img = os.path.join(OUTPUT_DIR, f"{sc['id']}.png")
        scene_audio = os.path.join(OUTPUT_DIR, f"{sc['id']}.mp3")
        scene_mp4 = os.path.join(OUTPUT_DIR, f"{sc['id']}.mp4")

        render_slide(sc, slide_img)
        generate_scene_audio(sc, scene_audio)
        render_scene_video(slide_img, scene_audio, scene_mp4)
        scene_videos.append(scene_mp4)

    concat_videos(scene_videos, FINAL_VIDEO)

if __name__ == "__main__":
    main()
