import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading, os, asyncio, subprocess, sys
import re

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

import edge_tts

VOICES = [
    ("US - Andrew (Male)", "en-US-AndrewNeural"),
    ("US - Andrew Multilingual (Male)", "en-US-AndrewMultilingualNeural"),
    ("US - Brian (Male)", "en-US-BrianNeural"),
    ("US - Brian Multilingual (Male)", "en-US-BrianMultilingualNeural"),
    ("US - Christopher (Male)", "en-US-ChristopherNeural"),
    ("US - Eric (Male)", "en-US-EricNeural"),
    ("US - Guy (Male)", "en-US-GuyNeural"),
    ("US - Roger (Male)", "en-US-RogerNeural"),
    ("US - Steffan (Male)", "en-US-SteffanNeural"),
    ("US - Ana (Female)", "en-US-AnaNeural"),
    ("US - Aria (Female)", "en-US-AriaNeural"),
    ("US - Ava (Female)", "en-US-AvaNeural"),
    ("US - Ava Multilingual (Female)", "en-US-AvaMultilingualNeural"),
    ("US - Emma (Female)", "en-US-EmmaNeural"),
    ("US - Emma Multilingual (Female)", "en-US-EmmaMultilingualNeural"),
    ("US - Jenny (Female)", "en-US-JennyNeural"),
    ("US - Michelle (Female)", "en-US-MichelleNeural"),
    ("GB - Ryan (Male)", "en-GB-RyanNeural"),
    ("GB - Thomas (Male)", "en-GB-ThomasNeural"),
    ("GB - Libby (Female)", "en-GB-LibbyNeural"),
    ("GB - Maisie (Female)", "en-GB-MaisieNeural"),
    ("GB - Sonia (Female)", "en-GB-SoniaNeural"),
    ("AU - William (Male)", "en-AU-WilliamMultilingualNeural"),
    ("AU - Natasha (Female)", "en-AU-NatashaNeural"),
    ("CA - Liam (Male)", "en-CA-LiamNeural"),
    ("CA - Clara (Female)", "en-CA-ClaraNeural"),
]

# Ensure cache directory exists
CACHE_DIR = os.path.expanduser("~/.sifmography/previews")
os.makedirs(CACHE_DIR, exist_ok=True)

async def _gen(text, voice, rate, path):
    comm = edge_tts.Communicate(text, voice, rate=f"{rate:+d}%")
    await comm.save(path)

def run_tts(text, voice, rate, path):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_gen(text, voice, rate, path))
    finally:
        loop.close()

def split_chapters(text):
    parts = re.split(r"(?i)\*?\*?\b(CHAPTER\s*\d+)\b\*?\*?", text)
    if len(parts) == 1:
        return [("full_script", text.strip())]
    chunks = []
    if parts[0].strip():
        chunks.append(("intro", parts[0].strip()))
    for i in range(1, len(parts), 2):
        label = parts[i].strip().lower().replace(" ", "_") 
        body = parts[i+1].strip() if (i+1) < len(parts) else ""
        if body:
            chunks.append((label, body))
    return chunks or [("full_script", text.strip())]

def split_by_length(text, max_words=3000):
    words = text.split()
    chunks = []
    current_chunk = []
    current_count = 0
    part_num = 1
    
    for w in words:
        current_chunk.append(w)
        current_count += 1
        
        # When we hit the target word count, wait for the next sentence ending to split safely
        if current_count >= max_words:
            if w.endswith('.') or w.endswith('!') or w.endswith('?') or w.endswith('."') or w.endswith('?"'):
                chunks.append((f"part_{part_num}", " ".join(current_chunk)))
                part_num += 1
                current_chunk = []
                current_count = 0
            # Failsafe: if there is zero punctuation in the transcript, force a split so we don't hang
            elif current_count >= max_words + 500:
                chunks.append((f"part_{part_num}", " ".join(current_chunk)))
                part_num += 1
                current_chunk = []
                current_count = 0
                
    if current_chunk:
        chunks.append((f"part_{part_num}", " ".join(current_chunk)))
        
    return chunks

class VoiceoverApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Voiceover Generator - Sifmography")
        self.geometry("850x800")
        self.minsize(800, 750)
        
        self.voice_var   = ctk.StringVar(value="US - Andrew (Male)")
        self.folder_var  = ctk.StringVar(value=os.path.expanduser("~/Desktop"))
        self.fname_var   = ctk.StringVar(value="voiceover")
        self.split_var   = ctk.StringVar(value="Auto-Split Massive Script (~3000 words per part)")
        self.rate_var    = ctk.IntVar(value=0)
        
        self.mode = "paste"
        self.loaded_path = ""
        
        self._ui()

    def _ui(self):
        self.title_label = ctk.CTkLabel(self, text="Voiceover Generator", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 5))
        
        self.subtitle_label = ctk.CTkLabel(self, text="Edge TTS | Free | YouTube Safe", font=ctk.CTkFont(size=12), text_color="gray")
        self.subtitle_label.pack(pady=(0, 15))

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.mode_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.mode_frame.pack(fill="x", pady=(0, 10))
        
        self.mode_seg = ctk.CTkSegmentedButton(self.mode_frame, values=["Paste Text", "Load File"], command=self._setmode)
        self.mode_seg.set("Paste Text")
        self.mode_seg.pack(side="left")

        self.ta_frame = ctk.CTkFrame(self.main_frame)
        self.ta_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.ta = ctk.CTkTextbox(self.ta_frame, font=ctk.CTkFont(size=14), wrap="word")
        self.ta.pack(fill="both", expand=True, padx=2, pady=2)
        self.ta.insert("1.0", "Paste your voiceover script here...")
        self.ta.bind("<FocusIn>", self._clr)

        self.file_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.file_lbl = ctk.CTkLabel(self.file_frame, text="No file selected", text_color="gray", anchor="w")
        self.file_lbl.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.btn_browse_file = ctk.CTkButton(self.file_frame, text="Browse File...", command=self._bfile, width=120)
        self.btn_browse_file.pack(side="right")

        self.settings_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.settings_frame.pack(fill="x", pady=10)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        # Voice Row
        ctk.CTkLabel(self.settings_frame, text="Voice:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        voice_controls = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        voice_controls.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.vcb = ctk.CTkOptionMenu(voice_controls, variable=self.voice_var, values=[v[0] for v in VOICES])
        self.vcb.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_preview = ctk.CTkButton(voice_controls, text="Preview Voice", width=100, fg_color="#1f538d", command=self._preview_voice)
        self.btn_preview.pack(side="right")

        # Speed Row
        ctk.CTkLabel(self.settings_frame, text="Speed:").grid(row=0, column=2, padx=10, pady=10, sticky="w")
        self.rate_slider = ctk.CTkSlider(self.settings_frame, from_=-30, to=50, variable=self.rate_var, number_of_steps=80, command=self._ratelbl)
        self.rate_slider.grid(row=0, column=3, padx=10, pady=10, sticky="ew")
        self.rate_lbl = ctk.CTkLabel(self.settings_frame, text="Normal", width=60)
        self.rate_lbl.grid(row=0, column=4, padx=5, pady=10, sticky="w")

        # Output Row
        ctk.CTkLabel(self.settings_frame, text="Save To:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(self.settings_frame, textvariable=self.folder_var).grid(row=1, column=1, columnspan=3, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(self.settings_frame, text="Browse", width=80, command=self._bfolder).grid(row=1, column=4, padx=10, pady=10)

        # Name Row
        ctk.CTkLabel(self.settings_frame, text="Name:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        name_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        name_frame.grid(row=2, column=1, columnspan=4, sticky="ew", padx=10, pady=10)
        
        ctk.CTkEntry(name_frame, textvariable=self.fname_var, width=200).pack(side="left")
        
        # Split Mode Dropdown
        split_options = [
            "Auto-Split Massive Script (~3000 words per part)",
            "Split by 'CHAPTER X' markers",
            "Do Not Split (Single File)"
        ]
        self.split_cb = ctk.CTkOptionMenu(name_frame, variable=self.split_var, values=split_options, width=320)
        self.split_cb.pack(side="left", padx=(20, 0))

        # Generate Button & Status
        self.gen_btn = ctk.CTkButton(self.main_frame, text="GENERATE VOICEOVER", font=ctk.CTkFont(size=16, weight="bold"), height=50, fg_color="green", hover_color="darkgreen", command=self._go)
        self.gen_btn.pack(fill="x", pady=(10, 10))

        self.progress_bar = ctk.CTkProgressBar(self.main_frame, mode="indeterminate")
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)

        self.status_lbl = ctk.CTkLabel(self.main_frame, text="Ready.", text_color="gray")
        self.status_lbl.pack()

    def _clr(self, e):
        if self.ta.get("1.0", "end-1c").strip() == "Paste your voiceover script here...":
            self.ta.delete("1.0", "end")

    def _setmode(self, value):
        self.mode = "paste" if value == "Paste Text" else "file"
        if self.mode == "paste":
            self.file_frame.pack_forget()
            self.ta_frame.pack(fill="both", expand=True, pady=(0, 10))
        else:
            self.ta_frame.pack_forget()
            self.file_frame.pack(fill="x", pady=(0, 10), expand=True)

    def _ratelbl(self, val):
        v = int(float(val))
        self.rate_lbl.configure(text="Normal" if v == 0 else (f"Faster +{v}%" if v > 0 else f"Slower {v}%"))

    def _bfile(self):
        p = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt *.md"), ("All", "*.*")])
        if p:
            self.loaded_path = p
            self.file_lbl.configure(text=os.path.basename(p), text_color="white")
            self.fname_var.set(os.path.splitext(os.path.basename(p))[0])

    def _bfolder(self):
        f = filedialog.askdirectory()
        if f:
            self.folder_var.set(f)

    def _gettext(self):
        if self.mode == "paste":
            t = self.ta.get("1.0", "end-1c").strip()
            return None if (not t or t == "Paste your voiceover script here...") else t
        if not self.loaded_path:
            return None
        try:
            with open(self.loaded_path, encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            messagebox.showerror("File Error", f"Could not read the file:\n{e}")
            return None

    def _preview_voice(self):
        if getattr(self, "is_working", False): return
        self.is_working = True
        
        voice_display = self.voice_var.get()
        voice = next((v for d, v in VOICES if d == voice_display), "en-US-AndrewNeural")
        rate = self.rate_var.get()
        sample_text = "Hello, this is a sample of what my voice sounds like. I hope this helps you choose the right narrator for your video."
        
        cache_filename = f"{voice}_speed_{rate}.mp3"
        out_path = os.path.join(CACHE_DIR, cache_filename)
        
        self.btn_preview.configure(state="disabled", text="Working...")
        self.gen_btn.configure(state="disabled")
        self.progress_bar.start()
        
        def work():
            try:
                if not os.path.exists(out_path):
                    self.after(0, lambda: self.status_lbl.configure(text="Generating fresh preview..."))
                    run_tts(sample_text, voice, rate, out_path)
                
                self.after(0, lambda: self.status_lbl.configure(text="Playing preview..."))
                subprocess.run(["afplay", out_path])
                self.after(0, lambda: self.status_lbl.configure(text="Ready."))
            except Exception as e:
                self.after(0, lambda err=e: self.status_lbl.configure(text=f"Error: {err}"))
            finally:
                self.is_working = False
                self.after(0, lambda: self.btn_preview.configure(state="normal", text="Preview Voice"))
                self.after(0, lambda: self.gen_btn.configure(state="normal"))
                self.after(0, self.progress_bar.stop)
                
        threading.Thread(target=work, daemon=True).start()

    def _go(self):
        if getattr(self, "is_working", False): return
        
        text = self._gettext()
        if not text:
            messagebox.showwarning("No Input", "Paste a script or load a file first.")
            return
            
        folder = self.folder_var.get().strip()
        if not os.path.isdir(folder):
            messagebox.showwarning("Bad Folder", "Choose a valid output folder.")
            return

        self.is_working = True
        self.gen_btn.configure(state="disabled", text="Generating...")
        self.btn_preview.configure(state="disabled")
        self.progress_bar.start()
        self.status_lbl.configure(text="Starting...")

        voice_display = self.voice_var.get()
        voice = next((v for d, v in VOICES if d == voice_display), "en-US-AndrewNeural")
        rate  = self.rate_var.get()
        base  = self.fname_var.get().strip() or "voiceover"
        split_mode = self.split_var.get()

        def work():
            try:
                if "Split" in split_mode and "Do Not" not in split_mode:
                    if "Auto-Split" in split_mode:
                        chunks = split_by_length(text, 3000)
                    else:
                        chunks = split_chapters(text)
                        
                    # Create parent folder for the parts
                    target_dir = os.path.join(folder, base)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    for i, (lbl, chunk) in enumerate(chunks, 1):
                        out = os.path.join(target_dir, f"{base}_{lbl}.mp3")
                        
                        # SMART RESUME: Skip if the file already exists and is not empty
                        if os.path.exists(out) and os.path.getsize(out) > 5000:
                            self.after(0, lambda l=lbl, i=i: self.status_lbl.configure(text=f"({i}/{len(chunks)}) Skipping {l} (Already exists)..."))
                            continue
                            
                        self.after(0, lambda l=lbl, i=i: self.status_lbl.configure(text=f"({i}/{len(chunks)}) Generating {l}..."))
                        run_tts(chunk, voice, rate, out)
                        
                    self.after(0, lambda: self.status_lbl.configure(text=f"Done! {len(chunks)} files saved to folder '{base}'"))
                    self.after(0, lambda: messagebox.showinfo("Done", f"Voiceover complete!\n\nAll parts were saved inside the '{base}' folder."))
                else:
                    out = os.path.join(folder, f"{base}.mp3")
                    self.after(0, lambda: self.status_lbl.configure(text="Generating audio..."))
                    run_tts(text, voice, rate, out)
                    self.after(0, lambda: self.status_lbl.configure(text=f"Done! Saved to {out}"))
                    self.after(0, lambda: messagebox.showinfo("Done", "Voiceover generation complete!"))
                
            except Exception as ex:
                self.after(0, lambda err=ex: self.status_lbl.configure(text=f"Error: {err}"))
                self.after(0, lambda err=ex: messagebox.showerror("Error", str(err)))
            finally:
                self.is_working = False
                self.after(0, self.progress_bar.stop)
                self.after(0, lambda: self.gen_btn.configure(state="normal", text="GENERATE VOICEOVER"))
                self.after(0, lambda: self.btn_preview.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

if __name__ == "__main__":
    app = VoiceoverApp()
    app.mainloop()
