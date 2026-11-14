import os
import sys
import subprocess
import json
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUTPUT_DIR = os.path.abspath(r"video_draft_short")
FINAL_VIDEO = os.path.abspath(r"RX6700XT_Prompt_Anatomy_Short_Draft.mp4")

os.makedirs(OUTPUT_DIR, exist_ok=True)

SCENES = [
    {
        "id": "scene1_input",
        "tag": "LOCAL LLM INFERENCE  •  RX 6700 XT",
        "title": "THE INPUT QUERY",
        "subtitle": "Anatomy of a Local AI Prompt",
        "boxes": [
            ("INPUT STRING", '> "What is the name of this computer?"', (0, 210, 255)),
            ("PROMPT CONTEXT", "System Flag: [Context Hostname = STRATA]\nTimestamp: 14:02:00.000 PST", (150, 150, 160)),
            ("TARGET HARDWARE", "PowerColor Fighter AMD Radeon RX 6700 XT 12GB\nNavi 22  •  Vulkan Driver  •  Windows 11", (0, 230, 150)),
        ],
        "speech": (
            "You ask: 'What is the name of this computer?' Hit Enter. Here is the path through the silicon."
        )
    },
    {
        "id": "scene2_tokenization",
        "tag": "STAGE 1  •  TOKENIZATION & VRAM",
        "title": "THE LINEUP & PINNING",
        "subtitle": "Discrete Integer IDs to Latent Vectors",
        "boxes": [
            ("TOKENIZER OUTPUT", "Text converted to integer IDs:\n[2061, 374, 279, 1438, 311, 428, 9063, 30]", (0, 210, 255)),
            ("EMBEDDING LOOKUP", "Maps each token ID into multi-dimensional latent space.", (255, 170, 0)),
            ("12 GB GDDR6 ADVANTAGE", "Full model weights & vocab resident in video memory.\nZero PCIe transfer latency. Zero system RAM paging.", (0, 230, 150)),
        ],
        "speech": (
            "Step one: Tokenization. Text becomes integer IDs. "
            "With 12 Gigabytes of GDDR6, all model weights stay pinned in VRAM—zero PCIe latency."
        )
    },
    {
        "id": "scene3_prefill",
        "tag": "STAGE 2  •  PROMPT PREFILL",
        "title": "COMPUTE-BOUND GEMM",
        "subtitle": "Parallel Ingestion Across 40 RDNA 2 CUs",
        "boxes": [
            ("PARALLEL INGESTION", "All 8 prompt tokens processed simultaneously.\nAttention calculated across the full sequence.", (0, 210, 255)),
            ("40 RDNA 2 COMPUTE UNITS", "40 Dual-Issue CUs clocked at 2,550 MHz.\nDual-issue FP16 matrix operations fire in parallel.", (255, 170, 0)),
            ("PREFILL LATENCY", "Sub-millisecond processing: Prompt is fully ingested.", (0, 230, 150)),
        ],
        "speech": (
            "Step two: Prefill. The GPU ingests the whole prompt at once. "
            "Forty RDNA 2 Compute Units fire FP16 matrix math in parallel at 2.5 Gigahertz."
        )
    },
    {
        "id": "scene4_kv_cache",
        "tag": "STAGE 3  •  KV CACHE & SRAM",
        "title": "THE BANDWIDTH SHOCK ABSORBER",
        "subtitle": "Switching to Memory-Bandwidth Bound",
        "boxes": [
            ("KEY-VALUE CACHE", "Attention keys and values written to memory.\nEvery subsequent word requires a full weight stream.", (255, 75, 75)),
            ("THE 192-BIT BUS LIMIT", "GDDR6 bus runs at 384 GB/s.\nA standard bottleneck for single-token reads.", (255, 170, 0)),
            ("96 MB INFINITY CACHE", "On-die L3 SRAM delivers over 1.0 TB/s throughput!\nShields the memory bus and slashes latency.", (0, 230, 150)),
        ],
        "speech": (
            "Step three: KV Cache. Generation becomes bandwidth-bound. "
            "The 96-Megabyte Infinity Cache delivers over one Terabyte per second of on-die SRAM throughput."
        )
    },
    {
        "id": "scene5_decode",
        "tag": "STAGE 4  •  GENERATION & TELEMETRY",
        "title": "AUTOREGRESSIVE DECODE",
        "subtitle": "Deterministic Forward Passes",
        "boxes": [
            ("GENERATED OUTPUT", '"This system is Strata."', (0, 210, 255)),
            ("LIVE TELEMETRY", "Speed: 72.4 Tokens/Second\nVRAM Allocation: 5.1 GiB  •  Board Power: 138 W", (0, 230, 150)),
            ("EFFICIENCY VERDICT", "Cold, fast, private execution on consumer gaming silicon.", (255, 170, 0)),
        ],
        "speech": (
            "Step four: Generation. One token per pass. "
            "Logits evaluated, next word predicted: 'This system is Strata.' 72 tokens per second."
        )
    },
    {
        "id": "scene6_end",
        "tag": "SUMMARY SPEC SHEET",
        "title": "AMD RADEON RX 6700 XT",
        "subtitle": "Local LLM Execution Verified",
        "boxes": [
            ("COMPUTE CAPACITY", "40 RDNA 2 Compute Units  •  2.55 GHz Boost Clock", (0, 210, 255)),
            ("MEMORY ARCHITECTURE", "12 GB GDDR6  •  96 MB On-Die Infinity Cache (>1 TB/s)", (0, 230, 150)),
            ("RESULT", "Desktop AI Performance on a $350 Gaming GPU", (255, 170, 0)),
        ],
        "speech": (
            "Navi 22. 40 Compute Units. 12 Gigabytes of VRAM. Just the facts."
        )
    }
]

def render_vertical_slide(scene, output_path):
    width, height = 1080, 1920
    im = Image.new("RGB", (width, height), (13, 17, 23)) # GitHub dark background
    draw = ImageDraw.Draw(im)

    # Accent top bar
    draw.rectangle([(0, 0), (width, 10)], fill=(0, 210, 255))

    # Subtle tech background grid
    for y in range(100, height, 120):
        draw.line([(0, y), (width, y)], fill=(22, 27, 34), width=1)
    for x in range(60, width, 120):
        draw.line([(x, 0), (x, height)], fill=(22, 27, 34), width=1)

    # Fonts
    try:
        font_tag = ImageFont.truetype("arialbd.ttf", 26)
        font_title = ImageFont.truetype("arialbd.ttf", 52)
        font_sub = ImageFont.truetype("arial.ttf", 30)
        font_box_header = ImageFont.truetype("arialbd.ttf", 30)
        font_box_body = ImageFont.truetype("consola.ttf", 26)
        font_footer = ImageFont.truetype("arial.ttf", 22)
    except:
        font_tag = font_title = font_sub = font_box_header = font_box_body = font_footer = ImageFont.load_default()

    # Tag Badge
    tag_text = scene["tag"]
    draw.rounded_rectangle([(60, 90), (60 + len(tag_text) * 16 + 30, 140)], radius=8, fill=(26, 35, 50), outline=(50, 100, 160), width=1)
    draw.text((75, 100), tag_text, font=font_tag, fill=(0, 210, 255))

    # Main Title & Subtitle
    draw.text((60, 165), scene["title"], font=font_title, fill=(240, 246, 252))
    draw.text((60, 235), scene["subtitle"], font=font_sub, fill=(139, 148, 158))

    # Info Cards / Boxes (3 vertical cards spaced out across 1920h)
    box_y = 330
    box_height = 360
    gap = 45

    for i, (b_title, b_body, accent_color) in enumerate(scene["boxes"]):
        cur_y = box_y + i * (box_height + gap)
        # Card background
        draw.rounded_rectangle([(60, cur_y), (width - 60, cur_y + box_height)], radius=16, fill=(22, 27, 34), outline=(48, 54, 61), width=2)
        # Left accent stripe
        draw.rounded_rectangle([(60, cur_y), (74, cur_y + box_height)], radius=8, fill=accent_color)
        
        # Card Header
        draw.text((105, cur_y + 40), b_title, font=font_box_header, fill=accent_color)
        
        # Card Body lines
        lines = b_body.split("\n")
        line_y = cur_y + 115
        for l in lines:
            draw.text((105, line_y), l, font=font_box_body, fill=(230, 237, 243))
            line_y += 52

    # Footer
    footer_text = "STRATA LABS  •  LOCAL LLM ARCHITECTURE  •  YOUTUBE SHORTS DRAFT"
    draw.text((60, height - 80), footer_text, font=font_footer, fill=(110, 118, 129))

    im.save(output_path, "PNG")

def generate_scene_audio(scene, audio_path):
    cmd = [
        "edge-tts",
        "--voice", "en-US-ChristopherNeural",
        "--rate", "+20%",
        "--text", scene["speech"],
        "--write-media", audio_path
    ]
    subprocess.run(cmd, check=True)

def get_audio_duration(path):
    res = subprocess.run([FFMPEG, "-i", path], stderr=subprocess.PIPE, text=True)
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d\.]+)", res.stderr)
    if m:
        return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
    return 10.0

def render_scene_video(image_path, audio_path, video_path):
    dur = get_audio_duration(audio_path)
    cmd = [
        FFMPEG,
        "-y",
        "-loop", "1",
        "-t", str(dur),
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(dur),
        video_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def concat_videos(scene_videos, final_output):
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

def main():
    scene_videos = []
    for i, sc in enumerate(SCENES):
        slide_img = os.path.join(OUTPUT_DIR, f"{sc['id']}.png")
        scene_audio = os.path.join(OUTPUT_DIR, f"{sc['id']}.mp3")
        scene_mp4 = os.path.join(OUTPUT_DIR, f"{sc['id']}.mp4")

        render_vertical_slide(sc, slide_img)
        generate_scene_audio(sc, scene_audio)
        render_scene_video(slide_img, scene_audio, scene_mp4)
        scene_videos.append(scene_mp4)

    concat_videos(scene_videos, FINAL_VIDEO)
    print(f"\nSUCCESS: Draft created at {FINAL_VIDEO}")

if __name__ == "__main__":
    main()
