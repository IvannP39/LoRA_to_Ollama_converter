"""
LoRA to Ollama Converter
========================
Application GUI permettant de convertir un LoRA fine-tuned en modèle Ollama.

Auteur: Ivann
Date: 2025-12-19
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import subprocess
import os
import threading
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES ET TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "ChatML (Qwen, etc.)": '''{{- if .System }}
<|im_start|>system
{{ .System }}<|im_end|>
{{- end }}
{{- if .Prompt }}
<|im_start|>user
{{ .Prompt }}<|im_end|>
{{- end }}
<|im_start|>assistant
{{ .Response }}<|im_end|>''',
    
    "Llama 3": '''{{- if .System }}<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|>{{- end }}{{- if .Prompt }}<|start_header_id|>user<|end_header_id|}

{{ .Prompt }}<|eot_id|>{{- end }}<|start_header_id|>assistant<|end_header_id|>

{{ .Response }}<|eot_id|>''',
    
    "Mistral/Mixtral": '''[INST] {{ if .System }}{{ .System }} {{ end }}{{ .Prompt }} [/INST] {{ .Response }}''',
    
    "Alpaca": '''{{ if .System }}### System:
{{ .System }}

{{ end }}### Instruction:
{{ .Prompt }}

### Response:
{{ .Response }}''',

    "Vicuna": '''{{ if .System }}{{ .System }}

{{ end }}USER: {{ .Prompt }}
ASSISTANT: {{ .Response }}''',

    "Custom": ""
}

STOP_TOKENS = {
    "ChatML (Qwen, etc.)": ["<|im_start|>", "<|im_end|>"],
    "Llama 3": ["<|eot_id|>", "<|start_header_id|>"],
    "Mistral/Mixtral": ["[INST]", "[/INST]"],
    "Alpaca": ["### Instruction:", "### Response:"],
    "Vicuna": ["USER:", "ASSISTANT:"],
    "Custom": []
}

# ═══════════════════════════════════════════════════════════════════════════════
# COULEURS ET STYLES
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_medium": "#16213e",
    "bg_light": "#0f3460",
    "accent": "#e94560",
    "accent_hover": "#ff6b6b",
    "text": "#eaeaea",
    "text_dim": "#a0a0a0",
    "success": "#4ecca3",
    "warning": "#ffc107",
    "error": "#ff6b6b",
    "input_bg": "#2a2a4a",
    "border": "#3a3a5a"
}


class ModernEntry(tk.Entry):
    """Entry personnalisé avec style moderne"""
    def __init__(self, parent, placeholder="", **kwargs):
        super().__init__(parent, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = COLORS["text_dim"]
        self.default_fg = COLORS["text"]
        
        self.configure(
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            highlightthickness=2,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"]
        )
        
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        
        self._show_placeholder()
    
    def _show_placeholder(self):
        if not self.get():
            self.insert(0, self.placeholder)
            self.configure(fg=self.placeholder_color)
    
    def _on_focus_in(self, event):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.configure(fg=self.default_fg)
    
    def _on_focus_out(self, event):
        if not self.get():
            self._show_placeholder()
    
    def get_value(self):
        """Retourne la valeur réelle (pas le placeholder)"""
        value = self.get()
        return "" if value == self.placeholder else value


class ModernButton(tk.Button):
    """Bouton personnalisé avec effets hover"""
    def __init__(self, parent, text, command=None, style="primary", **kwargs):
        colors = {
            "primary": (COLORS["accent"], COLORS["accent_hover"]),
            "secondary": (COLORS["bg_light"], COLORS["accent"]),
            "success": (COLORS["success"], "#6ecca3")
        }
        self.bg_normal, self.bg_hover = colors.get(style, colors["primary"])
        
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=self.bg_normal,
            fg=COLORS["text"],
            activebackground=self.bg_hover,
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=20,
            pady=8,
            **kwargs
        )
        
        self.bind("<Enter>", lambda e: self.configure(bg=self.bg_hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self.bg_normal))


class LoraToOllamaApp:
    """Application principale"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🦙 LoRA to Ollama Converter")
        self.root.geometry("740x600")
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.resizable(True, True)
        
        # Variables
        self.is_processing = False
        
        # Style ttk
        self.setup_styles()
        
        # Interface
        self.create_widgets()
        
        # Centrer la fenêtre
        self.center_window()
    
    def setup_styles(self):
        """Configure les styles ttk"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Modern.TCombobox",
            fieldbackground=COLORS["input_bg"],
            background=COLORS["input_bg"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"]
        )
        
        style.map("Modern.TCombobox",
            fieldbackground=[("readonly", COLORS["input_bg"])],
            selectbackground=[("readonly", COLORS["accent"])],
            selectforeground=[("readonly", COLORS["text"])]
        )
    
    def center_window(self):
        """Centre la fenêtre à l'écran"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_widgets(self):
        """Crée tous les widgets de l'interface"""
        # Container principal avec scroll
        main_canvas = tk.Canvas(self.root, bg=COLORS["bg_dark"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        self.main_frame = tk.Frame(main_canvas, bg=COLORS["bg_dark"])
        
        self.main_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)
        
        # Header
        self.create_header()
        
        # Sections
        self.create_lora_section()
        self.create_base_model_section()
        self.create_llama_cpp_section()
        self.create_modelfile_section()
        self.create_output_section()
        self.create_action_buttons()
        self.create_log_section()
    
    def create_header(self):
        """Crée le header de l'application"""
        header = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        header.pack(fill="x", padx=30, pady=(20, 10))
        
        # Titre avec gradient effect (simulé)
        title = tk.Label(
            header,
            text="🦙 LoRA to Ollama Converter",
            font=("Segoe UI", 24, "bold"),
            bg=COLORS["bg_dark"],
            fg=COLORS["accent"]
        )
        title.pack()
        
        subtitle = tk.Label(
            header,
            text="Convertissez vos modèles LoRA fine-tuned en modèles Ollama",
            font=("Segoe UI", 11),
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"]
        )
        subtitle.pack(pady=(5, 0))
        
        # Séparateur
        sep = tk.Frame(header, height=2, bg=COLORS["accent"])
        sep.pack(fill="x", pady=(15, 0))
    
    def create_section_frame(self, title, icon="📁"):
        """Crée un frame de section avec titre"""
        section = tk.Frame(self.main_frame, bg=COLORS["bg_medium"], relief="flat")
        section.pack(fill="x", padx=30, pady=10)
        
        # Header de section
        header = tk.Frame(section, bg=COLORS["bg_medium"])
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        tk.Label(
            header,
            text=f"{icon} {title}",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).pack(side="left")
        
        # Content frame
        content = tk.Frame(section, bg=COLORS["bg_medium"])
        content.pack(fill="x", padx=15, pady=(0, 15))
        
        return content
    
    def create_path_input(self, parent, label, placeholder, row, filetypes=None, is_directory=False):
        """Crée une ligne d'entrée de chemin avec bouton browse"""
        tk.Label(
            parent,
            text=label,
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"],
            anchor="w"
        ).grid(row=row, column=0, sticky="w", pady=(5, 2))
        
        frame = tk.Frame(parent, bg=COLORS["bg_medium"])
        frame.grid(row=row+1, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        
        entry = ModernEntry(frame, placeholder=placeholder)
        entry.grid(row=0, column=0, sticky="ew", ipady=5)
        
        def browse():
            if is_directory:
                path = filedialog.askdirectory()
            else:
                path = filedialog.askopenfilename(filetypes=filetypes or [("All files", "*.*")])
            if path:
                entry.delete(0, tk.END)
                entry.configure(fg=COLORS["text"])
                entry.insert(0, path)
        
        btn = ModernButton(frame, text="📂", command=browse, style="secondary")
        btn.grid(row=0, column=1, padx=(10, 0))
        
        return entry
    
    def create_lora_section(self):
        """Section LoRA files"""
        content = self.create_section_frame("Fichiers LoRA", "🔧")
        content.columnconfigure(0, weight=1)
        
        self.adapter_model_entry = self.create_path_input(
            content,
            "Chemin vers adapter_model.safetensors :",
            "C:/path/to/adapter_model.safetensors",
            0,
            [("SafeTensors", "*.safetensors"), ("All files", "*.*")]
        )
        
        self.adapter_config_entry = self.create_path_input(
            content,
            "Chemin vers adapter_config.json :",
            "C:/path/to/adapter_config.json",
            2,
            [("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        # Section pour base_model_name_or_path
        tk.Label(
            content,
            text="base_model_name_or_path (dans adapter_config.json) :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"],
            anchor="w"
        ).grid(row=4, column=0, sticky="w", pady=(10, 2))
        
        base_model_frame = tk.Frame(content, bg=COLORS["bg_medium"])
        base_model_frame.grid(row=5, column=0, sticky="ew", pady=(0, 5))
        base_model_frame.columnconfigure(0, weight=1)
        
        self.base_model_path_entry = ModernEntry(base_model_frame, placeholder="Charger depuis adapter_config.json...")
        self.base_model_path_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        
        load_btn = ModernButton(base_model_frame, text="🔄 Charger", command=self.load_current_base_model, style="secondary")
        load_btn.grid(row=0, column=1, padx=(10, 0))
        
        # Label d'information
        self.base_model_info_label = tk.Label(
            content,
            text="💡 Cliquez sur 'Charger' après avoir sélectionné adapter_config.json",
            font=("Segoe UI", 9, "italic"),
            bg=COLORS["bg_medium"],
            fg=COLORS["text_dim"]
        )
        self.base_model_info_label.grid(row=6, column=0, sticky="w")
    
    def load_current_base_model(self):
        """Charge la valeur actuelle de base_model_name_or_path depuis adapter_config.json"""
        config_path = self.adapter_config_entry.get_value()
        
        if not config_path:
            messagebox.showwarning("Attention", "Veuillez d'abord sélectionner le fichier adapter_config.json")
            return
        
        if not os.path.exists(config_path):
            messagebox.showerror("Erreur", f"Le fichier n'existe pas: {config_path}")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            current_value = config.get("base_model_name_or_path", "")
            
            # Mettre à jour le champ
            self.base_model_path_entry.delete(0, tk.END)
            self.base_model_path_entry.configure(fg=COLORS["text"])
            self.base_model_path_entry.insert(0, current_value)
            
            # Mettre à jour le label d'info
            self.base_model_info_label.configure(
                text=f"✅ Valeur chargée. Modifiez si nécessaire (ex: enlever '-bnb-4bit')",
                fg=COLORS["success"]
            )
            
            self.log(f"base_model_name_or_path chargé: {current_value}", "info")
            
        except json.JSONDecodeError:
            messagebox.showerror("Erreur", "Le fichier adapter_config.json n'est pas un JSON valide")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la lecture: {str(e)}")
    
    def create_base_model_section(self):
        """Section modèle de base"""
        content = self.create_section_frame("Modèle de Base", "🤖")
        content.columnconfigure(0, weight=1)
        
        # Type de modèle
        tk.Label(
            content,
            text="Type de source :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=0, sticky="w", pady=(5, 2))
        
        self.model_source_var = tk.StringVar(value="huggingface")
        
        radio_frame = tk.Frame(content, bg=COLORS["bg_medium"])
        radio_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        for text, value in [("🌐 HuggingFace (téléchargement)", "huggingface"), ("💾 Fichier local (GGUF)", "local")]:
            rb = tk.Radiobutton(
                radio_frame,
                text=text,
                variable=self.model_source_var,
                value=value,
                bg=COLORS["bg_medium"],
                fg=COLORS["text"],
                selectcolor=COLORS["input_bg"],
                activebackground=COLORS["bg_medium"],
                activeforeground=COLORS["text"],
                font=("Segoe UI", 10),
                command=self.toggle_model_source
            )
            rb.pack(side="left", padx=(0, 20))
        
        # Frame pour HuggingFace
        self.hf_frame = tk.Frame(content, bg=COLORS["bg_medium"])
        self.hf_frame.grid(row=2, column=0, sticky="ew")
        self.hf_frame.columnconfigure(0, weight=1)
        
        tk.Label(
            self.hf_frame,
            text="Nom du repo HuggingFace (ex: unsloth/llama-3-8b) :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=0, sticky="w", pady=(5, 2))
        
        self.hf_repo_entry = ModernEntry(self.hf_frame, placeholder="organization/model-name")
        self.hf_repo_entry.grid(row=1, column=0, sticky="ew", ipady=5, pady=(0, 10))
        
        tk.Label(
            self.hf_frame,
            text="Token HuggingFace (pour modèles privés/gated) :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=2, column=0, sticky="w", pady=(5, 2))
        
        self.hf_token_entry = ModernEntry(self.hf_frame, placeholder="hf_xxxxxxxxxx")
        self.hf_token_entry.configure(show="*")
        self.hf_token_entry.grid(row=3, column=0, sticky="ew", ipady=5)
        
        # Frame pour fichier local
        self.local_frame = tk.Frame(content, bg=COLORS["bg_medium"])
        self.local_frame.columnconfigure(0, weight=1)
        
        self.local_model_entry = self.create_path_input(
            self.local_frame,
            "Chemin vers le modèle GGUF local :",
            "C:/path/to/model.gguf",
            0,
            [("GGUF files", "*.gguf"), ("All files", "*.*")]
        )
        
        # Masquer le frame local par défaut
        self.local_frame.grid_forget()
    
    def toggle_model_source(self):
        """Toggle entre HuggingFace et local"""
        if self.model_source_var.get() == "huggingface":
            self.local_frame.grid_forget()
            self.hf_frame.grid(row=2, column=0, sticky="ew")
        else:
            self.hf_frame.grid_forget()
            self.local_frame.grid(row=2, column=0, sticky="ew")
    
    def create_llama_cpp_section(self):
        """Section llama.cpp"""
        content = self.create_section_frame("llama.cpp", "⚡")
        content.columnconfigure(0, weight=1)
        
        self.llama_cpp_entry = self.create_path_input(
            content,
            "Chemin vers le dossier llama.cpp (laisser vide pour téléchargement auto) :",
            "C:/path/to/llama.cpp",
            0,
            is_directory=True
        )
        
        info_label = tk.Label(
            content,
            text="💡 Si non spécifié, llama.cpp sera cloné dans le dossier courant",
            font=("Segoe UI", 9, "italic"),
            bg=COLORS["bg_medium"],
            fg=COLORS["text_dim"]
        )
        info_label.grid(row=2, column=0, sticky="w")
    
    def create_modelfile_section(self):
        """Section configuration du Modelfile"""
        content = self.create_section_frame("Configuration Modelfile", "📝")
        content.columnconfigure(0, weight=1)
        
        # Template
        tk.Label(
            content,
            text="Template de conversation :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=0, sticky="w", pady=(5, 2))
        
        self.template_var = tk.StringVar(value="ChatML (Qwen, etc.)")
        template_combo = ttk.Combobox(
            content,
            textvariable=self.template_var,
            values=list(TEMPLATES.keys()),
            state="readonly",
            style="Modern.TCombobox",
            font=("Segoe UI", 10)
        )
        template_combo.grid(row=1, column=0, sticky="ew", pady=(0, 10), ipady=5)
        template_combo.bind("<<ComboboxSelected>>", self.on_template_change)
        
        # Custom template text
        tk.Label(
            content,
            text="Template personnalisé (éditable si 'Custom' sélectionné) :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=2, column=0, sticky="w", pady=(5, 2))
        
        self.template_text = scrolledtext.ScrolledText(
            content,
            height=6,
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Consolas", 9),
            relief="flat",
            state="disabled"
        )
        self.template_text.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.template_text.insert("1.0", TEMPLATES["ChatML (Qwen, etc.)"])
        
        # System prompt
        tk.Label(
            content,
            text="System Prompt (optionnel) :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=4, column=0, sticky="w", pady=(5, 2))
        
        self.system_text = scrolledtext.ScrolledText(
            content,
            height=3,
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 10),
            relief="flat"
        )
        self.system_text.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        
        # Parameters
        params_frame = tk.Frame(content, bg=COLORS["bg_medium"])
        params_frame.grid(row=6, column=0, sticky="ew", pady=(5, 0))
        params_frame.columnconfigure((0, 1, 2, 3), weight=1)
        
        tk.Label(
            params_frame,
            text="Temperature :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=0, sticky="w")
        
        self.temp_entry = ModernEntry(params_frame, placeholder="0.7")
        self.temp_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), ipady=5)
        
        tk.Label(
            params_frame,
            text="Top P :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=1, sticky="w")
        
        self.top_p_entry = ModernEntry(params_frame, placeholder="0.9")
        self.top_p_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10), ipady=5)
        
        tk.Label(
            params_frame,
            text="Top K :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=2, sticky="w")
        
        self.top_k_entry = ModernEntry(params_frame, placeholder="40")
        self.top_k_entry.grid(row=1, column=2, sticky="ew", padx=(0, 10), ipady=5)
        
        tk.Label(
            params_frame,
            text="Num Ctx :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=3, sticky="w")
        
        self.num_ctx_entry = ModernEntry(params_frame, placeholder="4096")
        self.num_ctx_entry.grid(row=1, column=3, sticky="ew", ipady=5)
    
    def on_template_change(self, event=None):
        """Callback quand le template change"""
        template_name = self.template_var.get()
        self.template_text.configure(state="normal")
        self.template_text.delete("1.0", tk.END)
        self.template_text.insert("1.0", TEMPLATES[template_name])
        
        if template_name == "Custom":
            self.template_text.configure(state="normal")
        else:
            self.template_text.configure(state="disabled")
    
    def create_output_section(self):
        """Section output"""
        content = self.create_section_frame("Sortie", "🎯")
        content.columnconfigure(0, weight=1)
        
        tk.Label(
            content,
            text="Nom du modèle Ollama final :",
            font=("Segoe UI", 10),
            bg=COLORS["bg_medium"],
            fg=COLORS["text"]
        ).grid(row=0, column=0, sticky="w", pady=(5, 2))
        
        self.model_name_entry = ModernEntry(content, placeholder="my-custom-model")
        self.model_name_entry.grid(row=1, column=0, sticky="ew", ipady=5, pady=(0, 10))
        
        # Output directory
        self.output_dir_entry = self.create_path_input(
            content,
            "Dossier de sortie pour les fichiers générés :",
            "C:/path/to/output",
            2,
            is_directory=True
        )
    
    def create_action_buttons(self):
        """Crée les boutons d'action"""
        btn_frame = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        btn_frame.pack(fill="x", padx=30, pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(btn_frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 15))
        
        # Boutons
        buttons_container = tk.Frame(btn_frame, bg=COLORS["bg_dark"])
        buttons_container.pack()
        
        self.convert_btn = ModernButton(
            buttons_container,
            text="🚀 Convertir et Créer le Modèle",
            command=self.start_conversion,
            style="primary"
        )
        self.convert_btn.pack(side="left", padx=5)
        
        ModernButton(
            buttons_container,
            text="🧹 Réinitialiser",
            command=self.reset_form,
            style="secondary"
        ).pack(side="left", padx=5)
    
    def create_log_section(self):
        """Section logs"""
        content = self.create_section_frame("Logs", "📋")
        content.columnconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            content,
            height=10,
            bg=COLORS["input_bg"],
            fg=COLORS["text"],
            font=("Consolas", 9),
            relief="flat",
            state="disabled"
        )
        self.log_text.grid(row=0, column=0, sticky="ew")
        
        # Tags pour les couleurs
        self.log_text.tag_configure("info", foreground=COLORS["text"])
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("error", foreground=COLORS["error"])
    
    def log(self, message, level="info"):
        """Ajoute un message au log"""
        self.log_text.configure(state="normal")
        prefix = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "")
        self.log_text.insert(tk.END, f"{prefix} {message}\n", level)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()
    
    def reset_form(self):
        """Réinitialise le formulaire"""
        for entry in [self.adapter_model_entry, self.adapter_config_entry, 
                      self.hf_repo_entry, self.hf_token_entry, self.llama_cpp_entry, 
                      self.model_name_entry, self.output_dir_entry,
                      self.temp_entry, self.top_p_entry, self.top_k_entry, self.num_ctx_entry]:
            entry.delete(0, tk.END)
            entry._show_placeholder()
        
        self.system_text.delete("1.0", tk.END)
        self.template_var.set("ChatML (Qwen, etc.)")
        self.on_template_change()
        
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        
        self.log("Formulaire réinitialisé", "info")
    
    def validate_inputs(self):
        """Valide les entrées utilisateur"""
        errors = []
        
        if not self.adapter_model_entry.get_value():
            errors.append("Le chemin vers adapter_model.safetensors est requis")
        elif not os.path.exists(self.adapter_model_entry.get_value()):
            errors.append("Le fichier adapter_model.safetensors n'existe pas")
        
        if not self.adapter_config_entry.get_value():
            errors.append("Le chemin vers adapter_config.json est requis")
        elif not os.path.exists(self.adapter_config_entry.get_value()):
            errors.append("Le fichier adapter_config.json n'existe pas")
        
        if self.model_source_var.get() == "huggingface":
            if not self.hf_repo_entry.get_value():
                errors.append("Le nom du repo HuggingFace est requis")
        else:
            if not self.local_model_entry.get_value():
                errors.append("Le chemin vers le modèle local est requis")
            elif not os.path.exists(self.local_model_entry.get_value()):
                errors.append("Le fichier du modèle local n'existe pas")
        
        if not self.model_name_entry.get_value():
            errors.append("Le nom du modèle Ollama est requis")
        
        return errors
    
    def start_conversion(self):
        """Démarre le processus de conversion"""
        if self.is_processing:
            return
        
        errors = self.validate_inputs()
        if errors:
            messagebox.showerror("Erreurs de validation", "\n".join(errors))
            return
        
        self.is_processing = True
        self.convert_btn.configure(state="disabled")
        self.progress.start()
        
        # Lancer dans un thread séparé
        thread = threading.Thread(target=self.run_conversion)
        thread.daemon = True
        thread.start()
    
    def run_conversion(self):
        """Exécute le processus de conversion complet"""
        try:
            # 1. Modifier adapter_config.json
            self.log("Modification de adapter_config.json...", "info")
            self.update_adapter_config()
            
            # 2. Préparer llama.cpp
            self.log("Vérification de llama.cpp...", "info")
            llama_cpp_path = self.prepare_llama_cpp()
            
            # 3. Préparer le modèle de base
            self.log("Préparation du modèle de base...", "info")
            base_model_path = self.prepare_base_model()
            
            # 4. Convertir LoRA en GGUF
            self.log("Conversion du LoRA en GGUF...", "info")
            lora_gguf_path = self.convert_lora_to_gguf(llama_cpp_path)
            
            # 5. Générer le Modelfile
            self.log("Génération du Modelfile...", "info")
            modelfile_path = self.generate_modelfile(base_model_path, lora_gguf_path)
            
            # 6. Créer le modèle Ollama
            self.log("Création du modèle Ollama...", "info")
            self.create_ollama_model(modelfile_path)
            
            self.log("🎉 Conversion terminée avec succès !", "success")
            self.log(f"Vous pouvez maintenant utiliser: ollama run {self.model_name_entry.get_value()}", "success")
            
        except Exception as e:
            self.log(f"Erreur: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
        finally:
            self.root.after(0, self.finish_conversion)
    
    def finish_conversion(self):
        """Termine le processus de conversion"""
        self.is_processing = False
        self.convert_btn.configure(state="normal")
        self.progress.stop()
    
    def update_adapter_config(self):
        """Met à jour le adapter_config.json avec le bon base_model_name_or_path"""
        config_path = self.adapter_config_entry.get_value()
        new_base_model = self.base_model_path_entry.get_value()
        
        if not new_base_model:
            self.log("base_model_name_or_path non modifié (champ vide)", "warning")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        old_base_model = config.get("base_model_name_or_path", "")
        
        # Ne modifier que si la valeur a changé
        if old_base_model == new_base_model:
            self.log(f"base_model_name_or_path inchangé: {old_base_model}", "info")
            return
        
        config["base_model_name_or_path"] = new_base_model
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        self.log(f"base_model_name_or_path modifié: {old_base_model} → {new_base_model}", "success")
    
    def prepare_llama_cpp(self):
        """Prépare llama.cpp (chemin existant ou téléchargement)"""
        llama_cpp_path = self.llama_cpp_entry.get_value()
        
        if llama_cpp_path and os.path.exists(llama_cpp_path):
            self.log(f"Utilisation de llama.cpp existant: {llama_cpp_path}", "success")
            return llama_cpp_path
        
        # Télécharger llama.cpp
        default_path = os.path.join(os.getcwd(), "llama.cpp")
        
        if os.path.exists(default_path):
            self.log(f"llama.cpp trouvé localement: {default_path}", "success")
            return default_path
        
        self.log("Téléchargement de llama.cpp (cela peut prendre un moment)...", "warning")
        
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/ggerganov/llama.cpp.git", default_path],
                capture_output=True,
                text=True,
                check=True
            )
            self.log("llama.cpp téléchargé avec succès", "success")
            return default_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"Erreur lors du téléchargement de llama.cpp: {e.stderr}")
        except FileNotFoundError:
            raise Exception("Git n'est pas installé. Veuillez installer Git ou spécifier le chemin vers llama.cpp.")
    
    def prepare_base_model(self):
        """Prépare le modèle de base (téléchargement HuggingFace ou chemin local)"""
        if self.model_source_var.get() == "local":
            path = self.local_model_entry.get_value()
            self.log(f"Utilisation du modèle local: {path}", "success")
            return path
        
        # Télécharger depuis HuggingFace
        repo_id = self.hf_repo_entry.get_value()
        token = self.hf_token_entry.get_value() or None
        
        try:
            from huggingface_hub import snapshot_download, hf_hub_download
            
            output_dir = self.output_dir_entry.get_value() or os.getcwd()
            model_dir = os.path.join(output_dir, repo_id.replace("/", "_"))
            
            self.log(f"Téléchargement du modèle depuis HuggingFace: {repo_id}...", "info")
            
            # Télécharger le modèle complet
            snapshot_download(
                repo_id=repo_id,
                local_dir=model_dir,
                token=token,
                local_dir_use_symlinks=False
            )
            
            self.log(f"Modèle téléchargé dans: {model_dir}", "success")
            return model_dir
            
        except ImportError:
            raise Exception("huggingface_hub n'est pas installé. Installez-le avec: pip install huggingface_hub")
        except Exception as e:
            raise Exception(f"Erreur lors du téléchargement du modèle: {str(e)}")
    
    def convert_lora_to_gguf(self, llama_cpp_path):
        """Convertit le LoRA en GGUF"""
        convert_script = os.path.join(llama_cpp_path, "convert_lora_to_gguf.py")
        
        if not os.path.exists(convert_script):
            raise Exception(f"Script de conversion non trouvé: {convert_script}")
        
        # Dossier contenant le LoRA
        lora_dir = os.path.dirname(self.adapter_model_entry.get_value())
        
        # Chemin de sortie
        output_dir = self.output_dir_entry.get_value() or lora_dir
        model_name = self.model_name_entry.get_value()
        output_file = os.path.join(output_dir, f"{model_name}-LoRA.gguf")
        
        self.log(f"Conversion en cours...", "info")
        
        try:
            result = subprocess.run(
                [sys.executable, convert_script, "--verbose", "--outfile", output_file, lora_dir],
                capture_output=True,
                text=True,
                cwd=llama_cpp_path
            )
            
            if result.returncode != 0:
                self.log(f"Stderr: {result.stderr}", "warning")
                raise Exception(f"Erreur de conversion: {result.stderr}")
            
            self.log(f"LoRA converti: {output_file}", "success")
            return output_file
            
        except Exception as e:
            raise Exception(f"Erreur lors de la conversion: {str(e)}")
    
    def generate_modelfile(self, base_model_path, lora_gguf_path):
        """Génère le Modelfile pour Ollama"""
        output_dir = self.output_dir_entry.get_value() or os.path.dirname(lora_gguf_path)
        model_name = self.model_name_entry.get_value()
        modelfile_path = os.path.join(output_dir, f"{model_name}.Modelfile")
        
        # Construire le contenu
        lines = []
        
        # FROM
        lines.append(f"FROM {base_model_path}")
        lines.append("")
        
        # ADAPTER
        lines.append(f"ADAPTER {lora_gguf_path}")
        lines.append("")
        
        # SYSTEM
        system_prompt = self.system_text.get("1.0", tk.END).strip()
        if system_prompt:
            lines.append(f'SYSTEM """')
            lines.append(system_prompt)
            lines.append('"""')
            lines.append("")
        
        # TEMPLATE
        template = self.template_text.get("1.0", tk.END).strip()
        if template:
            lines.append('TEMPLATE """')
            lines.append(template)
            lines.append('"""')
            lines.append("")
        
        # PARAMETERS
        temp = self.temp_entry.get_value()
        top_p = self.top_p_entry.get_value()
        top_k = self.top_k_entry.get_value()
        num_ctx = self.num_ctx_entry.get_value()
        
        if temp:
            lines.append(f"PARAMETER temperature {temp}")
        if top_p:
            lines.append(f"PARAMETER top_p {top_p}")
        if top_k:
            lines.append(f"PARAMETER top_k {top_k}")
        if num_ctx:
            lines.append(f"PARAMETER num_ctx {num_ctx}")
        
        # Stop tokens
        template_name = self.template_var.get()
        for stop_token in STOP_TOKENS.get(template_name, []):
            lines.append(f'PARAMETER stop "{stop_token}"')
        
        # Écrire le fichier
        with open(modelfile_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        self.log(f"Modelfile créé: {modelfile_path}", "success")
        return modelfile_path
    
    def create_ollama_model(self, modelfile_path):
        """Crée le modèle Ollama avec la commande ollama create"""
        model_name = self.model_name_entry.get_value()
        
        self.log(f"Exécution: ollama create {model_name} -f {modelfile_path}", "info")
        
        try:
            result = subprocess.run(
                ["ollama", "create", model_name, "-f", modelfile_path],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                self.log(result.stdout, "info")
            
            if result.returncode != 0:
                self.log(f"Stderr: {result.stderr}", "warning")
                raise Exception(f"Erreur ollama create: {result.stderr}")

            if self.verify_model_exists(model_name, 6, 20):
                self.log(f"✅ Modèle '{model_name}' créé et vérifié avec succès !", "success")
            else:
                self.log(f"⚠️ Le modèle semble créé mais n'apparaît pas dans 'ollama list'", "warning")
            
        except FileNotFoundError:
            raise Exception("Ollama n'est pas installé ou n'est pas dans le PATH. Veuillez installer Ollama.")
        except Exception as e:
            raise Exception(f"Erreur lors de la création du modèle: {str(e)}")


    def verify_model_exists(self, model_name, max_attempts=5, delay=2):
        """Vérifie que le modèle existe dans ollama list"""
        import time
        
        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    # Chercher le nom du modèle dans la sortie
                    lines = result.stdout.lower().split('\n')
                    for line in lines:
                        if model_name.lower() in line:
                            return True
                
                # Attendre avant la prochaine tentative
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                    
            except Exception as e:
                self.log(f"Erreur lors de la vérification: {str(e)}", "warning")
        
        return False


def main():
    root = tk.Tk()
    app = LoraToOllamaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
