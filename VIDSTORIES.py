import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
from PIL import Image, ImageTk
from moviepy.editor import ImageSequenceClip, AudioFileClip
from pydub import AudioSegment
from pydub.playback import play
import requests
from gtts import gTTS
import shutil
import uuid
import re
import json
import datetime
from openai import OpenAI


# Initialize OpenAI API
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

class MainGUI:
    def __init__(self, master):
        self.master = master
        master.title("Story and Dialogue Generator")
        master.geometry("780x870")

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.story_tab = ttk.Frame(self.notebook)
        self.voice_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.story_tab, text="Story/Dialogue Generator")
        self.notebook.add(self.voice_tab, text="Voice Tuning Studio")

        self.settings_file = "voice_settings.json"
        self.text_input_file = "text_input.txt"
        self.active_voice = tk.StringVar(value="Voice 1")
        self.audio_files = []
        self.voice_counters = {'Voice 1': 1, 'Voice 2': 1}
        self.playing_audio = None
        self.stop_playback = threading.Event()

        self.create_necessary_folders()
        self.load_settings()
        self.load_voice_counters()

        self.load_personas()
        self.create_story_widgets()
        self.create_voice_widgets()

        self.load_existing_files()
        self.load_text_input()

    def load_personas(self):
        self.personas = {
            "Default": "I am a friendly and free-thinking AI, here to assist and converse on a wide range of topics.",
            "Custom": self.load_custom_persona()
        }

    def load_custom_persona(self):
        try:
            with open("Persona.txt", "r", encoding="utf-8") as persona_file:
                return persona_file.read().strip()
        except FileNotFoundError:
            return "Custom persona file not found. Using default."

    def create_necessary_folders(self):
        folders = ['AUDIO', 'IMAGES', 'PROJECTS', 'DIALOGS', 'BACKUPS']
        for folder in folders:
            os.makedirs(folder, exist_ok=True)

    def update_setting(self, voice, param, value):
        param_key = param.lower().replace(' ', '_')
        self.settings[voice][param_key] = float(value)
        self.save_settings()
    
    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as f:
                self.settings = json.load(f)
        else:
            self.settings = {
                "Voice 1": {param.lower().replace(' ', '_'): 0 for param in ["pitch", "speed", "low_pass", "high_pass", "bass_boost", "formant_shift"]},
                "Voice 2": {param.lower().replace(' ', '_'): 0 for param in ["pitch", "speed", "low_pass", "high_pass", "bass_boost", "formant_shift"]}
            }
            self.settings["Voice 1"]["speed"] = 1
            self.settings["Voice 2"]["speed"] = 1
        self.save_settings()

    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f)

    def load_voice_counters(self):
        counter_file = "voice_counters.json"
        if os.path.exists(counter_file):
            with open(counter_file, 'r') as f:
                self.voice_counters = json.load(f)
        else:
            self.voice_counters = {'Voice 1': 1, 'Voice 2': 1}

    def save_voice_counters(self):
        counter_file = "voice_counters.json"
        with open(counter_file, 'w') as f:
            json.dump(self.voice_counters, f)

    def create_story_widgets(self):
        selection_frame = ttk.Frame(self.story_tab)
        selection_frame.pack(pady=5, padx=10, fill=tk.X)

        # Persona selection
        ttk.Label(selection_frame, text="Select Persona:").pack(side=tk.LEFT, padx=5)
        self.persona_var = tk.StringVar(value="Default")
        ttk.Combobox(selection_frame, textvariable=self.persona_var, 
                     values=list(self.personas.keys())).pack(side=tk.LEFT, padx=5)

        # Model selection
        ttk.Label(selection_frame, text="Select GPT Model:").pack(side=tk.LEFT, padx=5)
        self.model_var = tk.StringVar(value="gpt-4-turbo")
        ttk.Combobox(selection_frame, textvariable=self.model_var, 
                     values=["gpt-4o-mini", "gpt-4-turbo", "gpt-4o"]).pack(side=tk.LEFT, padx=5)

        # Voice selection
        ttk.Label(selection_frame, text="Select Voice:").pack(side=tk.LEFT, padx=5)
        self.voice_var = tk.StringVar(value="Voice 1")
        ttk.Combobox(selection_frame, textvariable=self.voice_var, 
                     values=["Voice 1", "Voice 2"]).pack(side=tk.LEFT, padx=5)

        # Input area
        ttk.Label(self.story_tab, text="Enter your story concept:").pack(pady=5)
        self.story_input_text = scrolledtext.ScrolledText(self.story_tab, height=5)
        self.story_input_text.pack(pady=5, padx=10, fill=tk.X)

        # Generate button
        ttk.Button(self.story_tab, text="Generate", command=self.generate_content).pack(pady=10)

        # Output area
        ttk.Label(self.story_tab, text="Generated Content:").pack(pady=5)
        self.output_text = scrolledtext.ScrolledText(self.story_tab, height=10)
        self.output_text.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)

        # Progress bar for video generation
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.story_tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(pady=5, padx=10, fill=tk.X)

        # Thumbnail filmstrip
        ttk.Label(self.story_tab, text="Generated Images:").pack(pady=5)
        self.filmstrip_frame = ttk.Frame(self.story_tab)
        self.filmstrip_frame.pack(pady=5, padx=10, fill=tk.X)

    def create_voice_widgets(self):
        main_frame = ttk.Frame(self.voice_tab, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.voice_tab.columnconfigure(0, weight=1)
        self.voice_tab.rowconfigure(0, weight=1)

        # Voice control frames
        voice_frame = ttk.Frame(main_frame)
        voice_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        voice_frame.columnconfigure(0, weight=1)
        voice_frame.columnconfigure(1, weight=1)

        voices = ["Voice 1", "Voice 2"]
        for i, voice in enumerate(voices):
            frame = ttk.LabelFrame(voice_frame, text=voice)
            frame.grid(row=0, column=i, padx=10, pady=10, sticky=(tk.N, tk.S, tk.E, tk.W))
            
            params = [
                ("Pitch", -5, 5, 0.1),
                ("Speed", 0.5, 1.5, 0.01),
                ("Low Pass", 0, 5000, 100),
                ("High Pass", 0, 1000, 50),
                ("Bass Boost", 0, 20, 1),
                ("Formant Shift", -5, 5, 0.1)
            ]
            
            for j, (param, min_val, max_val, step) in enumerate(params):
                ttk.Label(frame, text=param).grid(row=j, column=0, sticky=tk.W, padx=5, pady=2)
                
                scale_var = tk.DoubleVar(value=self.settings[voice][param.lower().replace(' ', '_')])
                scale = ttk.Scale(frame, from_=min_val, to=max_val, orient=tk.HORIZONTAL, length=200,
                                  variable=scale_var, command=lambda x, v=voice, p=param: self.update_setting(v, p, x))
                scale.grid(row=j, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))
                
                button_frame = ttk.Frame(frame)
                button_frame.grid(row=j, column=2, padx=5, pady=2)
                
                ttk.Button(button_frame, text="-", width=2,
                           command=lambda v=scale_var, s=step: self.adjust_value(v, -s)).pack(side=tk.LEFT)
                ttk.Button(button_frame, text="+", width=2,
                           command=lambda v=scale_var, s=step: self.adjust_value(v, s)).pack(side=tk.LEFT)
                
                setattr(self, f"{voice.lower().replace(' ', '')}_{param.lower().replace(' ', '_')}", scale_var)

        # Text input with word wrap and scrollbar
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(1, weight=1)

        ttk.Label(input_frame, text="Text Input:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        text_input_frame = ttk.Frame(input_frame)
        text_input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_input_frame.columnconfigure(0, weight=1)
        text_input_frame.rowconfigure(0, weight=1)

        self.text_input = tk.Text(text_input_frame, height=10, wrap=tk.WORD)
        self.text_input.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.text_input.bind('<KeyRelease>', self.on_text_change)
        self.text_input.bind('<Button-3>', self.show_text_context_menu)

        scrollbar = ttk.Scrollbar(text_input_frame, orient="vertical", command=self.text_input.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.text_input.configure(yscrollcommand=scrollbar.set)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        button_frame.columnconfigure(1, weight=1)

        ttk.Button(button_frame, text="Clear", command=self.clear_text_input).grid(row=0, column=0, sticky=tk.W)
        
        voice_button_frame = ttk.Frame(button_frame)
        voice_button_frame.grid(row=0, column=1)
        ttk.Radiobutton(voice_button_frame, text="Voice 1", variable=self.active_voice, value="Voice 1").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(voice_button_frame, text="Voice 2", variable=self.active_voice, value="Voice 2").pack(side=tk.LEFT, padx=5)
        ttk.Button(voice_button_frame, text="Test", command=self.test_voice).pack(side=tk.LEFT, padx=5)
        ttk.Button(voice_button_frame, text="Save", command=self.save_voice).pack(side=tk.LEFT, padx=5)

        # Progress bar and label
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        progress_frame.columnconfigure(1, weight=1)

        self.progress_label = ttk.Label(progress_frame, text="0/0", width=5)
        self.progress_label.grid(row=0, column=0, padx=(0, 5))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E))

        # File list
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=4, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        ttk.Label(list_frame, text="Saved Audio Files:").grid(row=0, column=0, sticky=tk.W)
        
        self.file_tree = ttk.Treeview(list_frame, columns=("Filename", "Size", "Date"), show="headings")
        self.file_tree.heading("Filename", text="Filename")
        self.file_tree.heading("Size", text="Size")
        self.file_tree.heading("Date", text="Date Created")
        self.file_tree.column("Filename", width=300, anchor="w")
        self.file_tree.column("Size", width=100, anchor="e")
        self.file_tree.column("Date", width=150, anchor="center")
        self.file_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.file_tree.bind('<Button-3>', self.show_file_context_menu)

        list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_tree.yview)
        list_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.file_tree.configure(yscrollcommand=list_scrollbar.set)

        # File action buttons
        file_button_frame = ttk.Frame(list_frame)
        file_button_frame.grid(row=2, column=0, pady=(5, 0))
        ttk.Button(file_button_frame, text="Play", command=self.play_selected_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Stop", command=self.stop_audio).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Open Location", command=self.open_file_location).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Rename", command=self.rename_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Copy", command=self.copy_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Delete", command=self.delete_file).pack(side=tk.LEFT, padx=5)

    def load_existing_files(self):
        self.audio_files = [os.path.join("DIALOGS", f) for f in os.listdir("DIALOGS") if f.endswith('.mp3')]
        self.audio_files.sort(key=self.sort_key)
        self.update_file_list()

    def play_selected_file(self):
        selection = self.file_tree.selection()
        if selection:
            file_path = self.audio_files[self.file_tree.index(selection[0])]
            self.stop_playback.clear()
            threading.Thread(target=self._play_audio, args=(file_path,)).start()

    def _play_audio(self, file_path):
        try:
            audio = AudioSegment.from_mp3(file_path)
            play(audio)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to play audio: {str(e)}")

    def stop_audio(self):
        if self.playing_audio:
            self.stop_playback.set()
            self.playing_audio = None

    def open_file_location(self):
        selection = self.file_tree.selection()
        if selection:
            file_path = self.audio_files[self.file_tree.index(selection[0])]
            os.startfile(os.path.dirname(file_path))

    def rename_file(self):
        selection = self.file_tree.selection()
        if selection:
            item = selection[0]
            old_name = self.file_tree.item(item, "values")[0]
            new_name = simpledialog.askstring("Rename File", "Enter new filename:", initialvalue=old_name)
            if new_name:
                old_path = os.path.join("DIALOGS", old_name)
                new_path = os.path.join("DIALOGS", new_name)
                try:
                    os.rename(old_path, new_path)
                    index = self.audio_files.index(old_path)
                    self.audio_files[index] = new_path
                    self.update_file_list()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to rename file: {str(e)}")

    def copy_file(self):
        selection = self.file_tree.selection()
        if selection:
            file_path = self.audio_files[self.file_tree.index(selection[0])]
            new_path = filedialog.asksaveasfilename(defaultextension=".mp3", initialfile=os.path.basename(file_path))
            if new_path:
                try:
                    shutil.copy(file_path, new_path)
                    self.audio_files.append(new_path)
                    self.update_file_list()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to copy file: {str(e)}")

    def delete_file(self):
        selection = self.file_tree.selection()
        if selection:
            file_path = self.audio_files[self.file_tree.index(selection[0])]
            if messagebox.askyesno("Delete File", f"Are you sure you want to delete {os.path.basename(file_path)}?"):
                try:
                    os.remove(file_path)
                    self.audio_files.remove(file_path)
                    self.update_file_list()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete file: {str(e)}")

    def sort_key(self, filename):
        basename = os.path.basename(filename)
        voice_match = re.match(r'(Voice \d+)', basename)
        voice = voice_match.group(1) if voice_match else ""
        
        number_match = re.search(r'\d+', basename)
        number = int(number_match.group()) if number_match else 0
        
        return (voice != "Voice 1", number, basename)

    def update_file_list(self):
        self.file_tree.delete(*self.file_tree.get_children())
        for file in self.audio_files:
            file_size = os.path.getsize(file)
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size/1024:.1f} KB"
            else:
                size_str = f"{file_size/(1024*1024):.1f} MB"
            
            create_date = datetime.datetime.fromtimestamp(os.path.getctime(file)).strftime('%Y-%m-%d %H:%M:%S')
            self.file_tree.insert("", "end", values=(os.path.basename(file), size_str, create_date))

    def on_text_change(self, event):
        self.save_text_input()

    def save_text_input(self):
        text = self.text_input.get("1.0", tk.END)
        with open(self.text_input_file, "w", encoding="utf-8") as f:
            f.write(text)

    def load_text_input(self):
        if os.path.exists(self.text_input_file):
            with open(self.text_input_file, "r", encoding="utf-8") as f:
                saved_text = f.read()
            self.text_input.delete("1.0", tk.END)
            self.text_input.insert(tk.END, saved_text)

    def show_text_context_menu(self, event):
        context_menu = tk.Menu(self.master, tearoff=0)
        context_menu.add_command(label="Copy", command=self.copy_text)
        context_menu.add_command(label="Cut", command=self.cut_text)
        context_menu.add_command(label="Paste", command=self.paste_text)
        context_menu.post(event.x_root, event.y_root)

    def copy_text(self):
        self.text_input.event_generate("<<Copy>>")

    def cut_text(self):
        self.text_input.event_generate("<<Cut>>")

    def paste_text(self):
        self.text_input.event_generate("<<Paste>>")

    def clear_text_input(self):
        self.text_input.delete("1.0", tk.END)
        self.save_text_input()

    def test_voice(self):
        self.process_voice(is_test=True)

    def save_voice(self):
        self.process_voice(is_test=False)

    def process_voice(self, is_test):
        try:
            sel_start = self.text_input.index(tk.SEL_FIRST)
            sel_end = self.text_input.index(tk.SEL_LAST)
            selected_text = self.text_input.get(sel_start, sel_end)
        except tk.TclError:
            sel_start = sel_end = None
            selected_text = ""
        
        if not selected_text:
            selected_text = self.text_input.get("1.0", tk.END).strip()
        
        if not selected_text:
            messagebox.showinfo("No Text", "Please enter or select some text to process.")
            return
        
        voice = self.active_voice.get()
        params = self.get_voice_params(voice)
        if is_test:
            threading.Thread(target=self._generate_and_play, args=(selected_text, voice, sel_start, sel_end), kwargs=params).start()
        else:
            threading.Thread(target=self._generate_and_save, args=(selected_text, voice, sel_start, sel_end), kwargs=params).start()

    def get_voice_params(self, voice):
        return {param: getattr(self, f"{voice.lower().replace(' ', '')}_{param}").get() 
                for param in ["pitch", "speed", "low_pass", "high_pass", "bass_boost", "formant_shift"]}

    def _generate_and_play(self, text, voice, sel_start, sel_end, **params):
        try:
            audio_path = generate_audio(text, voice, progress_callback=self.update_progress, **params)
            sound = AudioSegment.from_mp3(audio_path)
            play(sound)
            os.remove(audio_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate or play audio: {str(e)}")
        finally:
            self.restore_selection(sel_start, sel_end)
            self.reset_progress()

    def _generate_and_save(self, text, voice, sel_start, sel_end, **params):
        try:
            audio_path = generate_audio(text, voice, progress_callback=self.update_progress, **params)
            base_filename = f"{voice}_AUDIO_{self.voice_counters[voice]:05d}.mp3"
            save_path = self.get_unique_filename(os.path.join("DIALOGS", base_filename))
            shutil.move(audio_path, save_path)
            self.audio_files.append(save_path)
            self.master.after(0, self.update_file_list)
            self.voice_counters[voice] += 1
            self.save_voice_counters()
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Audio saved as {os.path.basename(save_path)}"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Failed to generate or save audio: {str(e)}"))
        finally:
            self.master.after(0, lambda: self.restore_selection(sel_start, sel_end))
            self.master.after(0, self.reset_progress)

    def update_progress(self, current, total=None):
        if total:
            progress = (current / total) * 100
        else:
            progress = current
        self.master.after(0, lambda: self.progress_var.set(progress))
        self.master.after(0, self.master.update_idletasks)

    def reset_progress(self):
        self.progress_var.set(0)
        self.progress_label.config(text="0/0")
        self.master.update_idletasks()

    def restore_selection(self, start, end):
        if start and end:
            self.text_input.tag_remove(tk.SEL, "1.0", tk.END)
            self.text_input.tag_add(tk.SEL, start, end)
            self.text_input.mark_set(tk.INSERT, end)
            self.text_input.see(tk.INSERT)
            self.text_input.focus_set()

    def generate_content(self):
        model_name = self.model_var.get()
        context = self.story_input_text.get("1.0", tk.END).strip()
        persona = self.personas[self.persona_var.get()]
        voice = self.voice_var.get()

        if not context:
            messagebox.showwarning("Input Required", "Please enter a story concept.")
            return

        self.output_text.delete("1.0", tk.END)
        self.progress_var.set(0)
        threading.Thread(target=self._generate_content, args=(model_name, context, persona, voice)).start()

    def _generate_content(self, model_name, context, persona, voice):
        try:
            self.update_progress(10)  # Initial progress
            content = chat_with_gpt(context, model_name, persona)
            
            if not content or "I'm sorry, but I can't assist with that." in content:
                self.master.after(0, lambda: messagebox.showinfo("Generation Failed", "The AI was unable to generate the requested content. Please try again with a different prompt."))
                return

            self.master.after(0, lambda: self.output_text.insert(tk.END, content))

            # Create project directory
            story_title = content.split('.')[0][:50].strip().replace(' ', '_')
            project_dir = os.path.join('PROJECTS', story_title)
            os.makedirs(project_dir, exist_ok=True)

            # Generate images and audio for the content
            self.update_progress(30)
            image_prompts = content.split(". ")
            image_paths = []
            for prompt in image_prompts:
                if prompt:
                    image_path = generate_image(prompt)
                    if image_path:
                        image_paths.append(image_path)

            self.master.after(0, lambda: self.display_thumbnails(image_paths))

            self.update_progress(50)
            audio_path = generate_audio(content, voice, progress_callback=self.update_progress)
            self.master.after(0, lambda: self.output_text.insert(tk.END, f"\n\nAudio generated: {audio_path}"))

            # Move audio file to project directory
            shutil.move(audio_path, os.path.join(project_dir, os.path.basename(audio_path)))

            # Compile video
            self.update_progress(70)
            self.compile_video(image_paths, os.path.join(project_dir, os.path.basename(audio_path)), project_dir)
            self.update_progress(100)

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {str(e)}"))

    def display_thumbnails(self, image_paths):
        for widget in self.filmstrip_frame.winfo_children():
            widget.destroy()

        for image_path in image_paths:
            img = Image.open(image_path)
            img.thumbnail((100, 100))
            img = ImageTk.PhotoImage(img)
            thumbnail = ttk.Label(self.filmstrip_frame, image=img)
            thumbnail.image = img
            thumbnail.pack(side=tk.LEFT, padx=5)

    def compile_video(self, image_paths, audio_path, project_dir):
        try:
            audio = AudioFileClip(audio_path)
            total_duration = audio.duration
            image_duration = total_duration / len(image_paths)
            clip = ImageSequenceClip(image_paths, durations=[image_duration] * len(image_paths))
            output_path = os.path.join(project_dir, f"final_video_{os.path.basename(project_dir)}.mp4")
            clip.set_fps(24).set_audio(audio).write_videofile(output_path, codec='libx264', audio_codec='aac')
            self.master.after(0, lambda: self.output_text.insert(tk.END, f"\n\nVideo created at: {output_path}"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Failed to compile video: {str(e)}"))

    def show_file_context_menu(self, event):
        item = self.file_tree.identify_row(event.y)
        if item:
            self.file_tree.selection_set(item)
            context_menu = tk.Menu(self.master, tearoff=0)
            context_menu.add_command(label="Play", command=self.play_selected_file)
            context_menu.add_command(label="Open Location", command=self.open_file_location)
            context_menu.add_command(label="Rename", command=self.rename_file)
            context_menu.add_command(label="Copy", command=self.copy_file)
            context_menu.add_command(label="Delete", command=self.delete_file)
            context_menu.post(event.x_root, event.y_root)


def chat_with_gpt(prompt, model_name, persona):
    messages = [
        {"role": "system", "content": persona},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_audio(text, voice, progress_callback=None, **params):
    print(f"\nGenerating audio using {voice}...")

    chunks = split_text(text)
    
    audio_segments = []
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(i, total_chunks)
        print(f"Processing chunk {i}/{total_chunks}")
        
        if voice == 'Voice 1':
            tld = 'co.uk'
        else:
            tld = 'com'
        
        tts = gTTS(text=chunk, lang='en', tld=tld, slow=False)
        
        temp_path = os.path.join("AUDIO", f"temp_{uuid.uuid4()}.mp3")
        tts.save(temp_path)
        
        audio_segment = AudioSegment.from_mp3(temp_path)
        audio_segment = modify_voice(audio_segment, **{k: v for k, v in params.items() if k != 'progress_callback'})
        
        audio_segments.append(audio_segment)
        os.remove(temp_path)
    
    print("Combining audio segments...")
    combined = sum(audio_segments)
    
    output_path = os.path.join("AUDIO", f"{voice}_{uuid.uuid4()}.mp3")
    combined.export(output_path, format="mp3")
    
    print(f"Audio generation complete. Saved to {output_path}")
    return output_path

def split_text(text, max_length=500):
    sentences = re.split('(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += " " + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def modify_voice(audio_segment, pitch=0, speed=1.0, low_pass=None, high_pass=None, bass_boost=0, formant_shift=0):
    audio_segment = audio_segment._spawn(audio_segment.raw_data, overrides={'frame_rate': int(audio_segment.frame_rate * speed)})
    
    if pitch != 0:
        new_sample_rate = int(audio_segment.frame_rate * (2.0 ** (pitch / 12.0)))
        audio_segment = audio_segment._spawn(audio_segment.raw_data, overrides={'frame_rate': new_sample_rate})
    
    if low_pass:
        audio_segment = audio_segment.low_pass_filter(low_pass)
    
    if high_pass:
        audio_segment = audio_segment.high_pass_filter(high_pass)
    
    if bass_boost > 0:
        bass_sound = audio_segment.low_pass_filter(200)
        audio_segment = audio_segment.overlay(bass_sound + bass_boost)
    
    if formant_shift != 0:
        formant_shift_factor = 2 ** (formant_shift / 12)
        audio_segment = audio_segment._spawn(audio_segment.raw_data, overrides={'frame_rate': int(audio_segment.frame_rate * formant_shift_factor)})
        audio_segment = audio_segment._spawn(audio_segment.raw_data, overrides={'frame_rate': int(audio_segment.frame_rate / formant_shift_factor)})

    return audio_segment

def generate_image(prompt):
    image_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
    response = requests.get(image_url)
    image_path = os.path.join("IMAGES", f"image_{uuid.uuid4()}.jpg")
    with open(image_path, 'wb') as file:
        file.write(response.content)
    return image_path

def main(use_gui=False):
    folders = ['AUDIO', 'IMAGES', 'PROJECTS', 'DIALOGS', 'BACKUPS']
    for folder in folders:
        os.makedirs(folder, exist_ok=True)

    if use_gui:
        root = tk.Tk()
        app = MainGUI(root)
        root.mainloop()

if __name__ == "__main__":
    main(use_gui=True)
