# -*- coding: utf-8 -*-
# =============================================================================
#
#   Arquivo: expanding_colony_generator.py (v9, correção do limite de nós)
#
# =============================================================================
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import numpy as np
from PIL import Image, ImageDraw, ImageTk
import random
import time
import threading
import queue
import imageio.v2 as imageio
import os
import tempfile
import shutil
import math

try:
    import noise # pip install noise
except ImportError:
    messagebox.showerror("Erro de Dependência", "A biblioteca 'noise' não está instalada.\nPor favor, execute: pip install noise")
    exit()


# =============================================================================
# NÚCLEO DO ALGORITMO DE GERAÇÃO
# =============================================================================
def run_fractal_generation(params, output_queue):
    frame_folder = tempfile.mkdtemp()
    frame_files = []
    
    try:
        width, height = params['width'], params['height']
        center = np.array([width / 2, height / 2])
        
        kill_distance = params['kill_distance']
        step_size = params['step_size']
        max_nodes = params['max_nodes']
        
        attractors_per_ring_base = params['attractors_per_ring_base']
        attractor_density_variation = params['attractor_density_variation']
        initial_radius = params['initial_radius']
        radius_step_base = params['radius_step_base']
        ring_irregularity = params['ring_irregularity']
        expansion_variation = params['expansion_variation']
        perlin_scale = params['perlin_scale']
        perlin_strength = params['perlin_strength']
        num_growth_lobes = params['num_growth_lobes']
        lobe_attractor_multiplier = params['lobe_attractor_multiplier']
        lobe_spread_angle = params['lobe_spread_angle']
        lobe_movement_factor = params['lobe_movement_factor']
        line_thickness = params['line_thickness']
        transparent_bg = params['transparent_bg']

        root = {'pos': center.copy(), 'parent': None}
        nodes = [root]
        attractors = []
        current_radius = initial_radius
        
        perlin_seed = random.randint(0, 10000)
        lobe_directions = [random.uniform(0, 2 * math.pi) for _ in range(num_growth_lobes)]

        output_queue.put({'status': 'Iniciando simulação...'})

        frame_count = 0
        while len(nodes) < max_nodes:
            if len(attractors) < attractors_per_ring_base * 0.1:
                actual_radius_step = radius_step_base * random.uniform(1 - expansion_variation, 1 + expansion_variation)
                actual_radius_step = max(1, actual_radius_step)
                
                output_queue.put({'status': f'Expandindo para o raio {current_radius:.0f} (passo {actual_radius_step:.1f})...'})

                num_attractors_this_ring_base = int(attractors_per_ring_base * random.uniform(1 - attractor_density_variation, 1 + attractor_density_variation))
                num_attractors_this_ring_base = max(1, num_attractors_this_ring_base)

                angles = []
                for _ in range(num_attractors_this_ring_base):
                    base_angle = random.uniform(0, 2 * math.pi)
                    cluster_factor = 0.5 * attractor_density_variation
                    deviated_angle = base_angle + random.uniform(-cluster_factor, cluster_factor)
                    angles.append(deviated_angle)

                for i in range(num_growth_lobes):
                    if lobe_movement_factor > 0:
                        lobe_directions[i] += random.uniform(-lobe_movement_factor, lobe_movement_factor) * math.pi / 180
                        lobe_directions[i] %= (2 * math.pi)

                    num_extra_attractors = int(attractors_per_ring_base * (lobe_attractor_multiplier - 1))
                    
                    for _ in range(num_extra_attractors):
                        lobe_angle = lobe_directions[i] + random.uniform(-lobe_spread_angle / 2, lobe_spread_angle / 2)
                        angles.append(lobe_angle)

                for angle in angles:
                    x_perlin = current_radius * math.cos(angle) / perlin_scale
                    y_perlin = current_radius * math.sin(angle) / perlin_scale
                    
                    perlin_value = noise.pnoise3(x_perlin, y_perlin, current_radius / perlin_scale, 
                                                octaves=4, persistence=0.5, lacunarity=2.0, repeatx=1024, repeaty=1024, base=perlin_seed)
                    
                    perlin_offset = (perlin_value + 1.0) / 2.0 * perlin_strength * radius_step_base
                    random_ring_offset = random.uniform(-radius_step_base * ring_irregularity, radius_step_base * ring_irregularity)
                    
                    individual_radius = current_radius + perlin_offset + random_ring_offset
                    individual_radius = max(1.0, individual_radius)

                    pos = center + np.array([math.cos(angle), math.sin(angle)]) * individual_radius
                    attractors.append(pos)
                
                current_radius += actual_radius_step

            growth_vectors = {i: [] for i in range(len(nodes))}
            for attractor in attractors:
                closest_node_index = -1; min_dist = float('inf')
                for i, node in enumerate(nodes):
                    d = np.linalg.norm(attractor - node['pos'])
                    if d < min_dist: min_dist = d; closest_node_index = i
                direction = attractor - nodes[closest_node_index]['pos']
                norm = np.linalg.norm(direction)
                if norm > 0: growth_vectors[closest_node_index].append(direction / norm)
            
            new_nodes = []
            for node_index, vectors in growth_vectors.items():
                # =================== MUDANÇA (CORREÇÃO DO LIMITE DE NÓS) ===================
                # Se a adição de mais nós for ultrapassar o limite, paramos de crescer nesta rodada.
                if len(nodes) + len(new_nodes) >= max_nodes:
                    break
                # =========================================================================
                if vectors:
                    avg_direction = np.mean(vectors, axis=0); norm = np.linalg.norm(avg_direction)
                    if norm > 0:
                        avg_direction /= norm; parent_node = nodes[node_index]
                        new_pos = parent_node['pos'] + avg_direction * step_size
                        new_node = {'pos': new_pos, 'parent': parent_node}; new_nodes.append(new_node)
            nodes.extend(new_nodes)
            
            surviving_attractors = []
            for attractor in attractors:
                closest_dist = min([np.linalg.norm(attractor - node['pos']) for node in nodes])
                if closest_dist > kill_distance: surviving_attractors.append(attractor)
            attractors = surviving_attractors

            progress = 100 * len(nodes) / max_nodes
            if len(nodes) // params['frame_interval'] > frame_count or len(nodes) >= max_nodes:
                frame_count += 1
                status_text = f"Nós: {len(nodes)}/{max_nodes} | Atratores: {len(attractors)}"
                output_queue.put({'status': status_text, 'progress': progress})

                if transparent_bg:
                    frame_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                else:
                    frame_image = Image.new('RGB', (width, height), params['bg_color'])
                draw = ImageDraw.Draw(frame_image)
                
                for node in nodes:
                    if node['parent']: p1 = node['parent']['pos']; p2 = node['pos']; draw.line((p1[0], p1[1], p2[0], p2[1]), fill=params['branch_color'], width=line_thickness)
                
                frame_path = os.path.join(frame_folder, f"frame_{frame_count:05d}.png")
                frame_image.save(frame_path)
                frame_files.append(frame_path)
                output_queue.put({'preview_frame': frame_image})

        output_queue.put({'status': f'Simulação concluída. Montando vídeo com {len(frame_files)} frames...'})
        
        # Lógica de criação do vídeo ...
        writer_params = {}
        output_format = 'mp4'

        if params['output_path'].lower().endswith('.webm') and transparent_bg:
            output_format = 'webm'
            writer_params = {'codec': 'libvpx-vp9', 'pixelformat': 'yuva420p', 'quality': 8, 'fps': 30}
        elif params['output_path'].lower().endswith('.webm'):
            output_format = 'webm'
            writer_params = {'codec': 'libvpx-vp9', 'quality': 8, 'fps': 30}
        else:
            writer_params = {'codec': 'libx264', 'quality': 8, 'fps': 30}
            
        with imageio.get_writer(params['output_path'], format=output_format, **writer_params) as writer:
            for filename in frame_files: writer.append_data(imageio.imread(filename))
        
        output_queue.put({'status': f'Concluído! Vídeo salvo em:\n{params["output_path"]}', 'progress': 100})

    except Exception as e:
        output_queue.put({'status': f'Erro: {e}', 'progress': 100})
        import traceback
        traceback.print_exc()
    finally:
        shutil.rmtree(frame_folder)


# =============================================================================
# CLASSE DA APLICAÇÃO TKINTER (GUI) - Nenhuma mudança necessária aqui
# =============================================================================
class FractalApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Gerador de Colônia Orgânica Assimétrica v9") # Atualizando o nome da janela
        self.master.geometry("1200x800")
        self.style = ttk.Style(); self.style.theme_use('clam')

        self.max_nodes = tk.IntVar(value=2000)
        self.attractors_per_ring_base = tk.IntVar(value=100)
        self.attractor_density_variation = tk.IntVar(value=20)
        self.initial_radius = tk.IntVar(value=50)
        self.radius_step_base = tk.IntVar(value=30)
        self.ring_irregularity = tk.IntVar(value=10)
        self.expansion_variation = tk.IntVar(value=30)
        self.perlin_scale = tk.IntVar(value=100)
        self.perlin_strength = tk.IntVar(value=80)
        self.num_growth_lobes = tk.IntVar(value=2)
        self.lobe_attractor_multiplier = tk.IntVar(value=200)
        self.lobe_spread_angle = tk.IntVar(value=30)
        self.lobe_movement_factor = tk.IntVar(value=5)
        self.kill_distance = tk.IntVar(value=10)
        self.step_size = tk.IntVar(value=5)
        self.frame_interval = tk.IntVar(value=20)
        self.line_thickness = tk.IntVar(value=1)
        self.transparent_bg = tk.BooleanVar(value=True) # Deixando a transparência como padrão
        
        self.bg_color = '#0a0a14'
        self.branch_color = '#ffffd0'
        
        self.generation_thread = None; self.queue = queue.Queue()

        self.main_frame = ttk.Frame(self.master, padding="10"); self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.controls_frame = ttk.LabelFrame(self.main_frame, text="Controles", padding="10", width=350); self.controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10)); self.controls_frame.pack_propagate(False)
        self.image_frame = ttk.LabelFrame(self.main_frame, text="Pré-visualização", padding="10"); self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.image_label = ttk.Label(self.image_frame, text="A pré-visualização da colônia aparecerá aqui.", anchor=tk.CENTER); self.image_label.pack(fill=tk.BOTH, expand=True)
        self.create_controls()

    def create_controls(self):
        f = ttk.Frame(self.controls_frame); f.pack(fill=tk.X, expand=True)
        f.columnconfigure(1, weight=1)

        current_row = 0
        self.create_slider(f, "Nº Máximo de Nós:", self.max_nodes, 200, 5000, current_row); current_row += 1
        self.create_slider(f, "Atratores (Base):", self.attractors_per_ring_base, 20, 500, current_row); current_row += 1
        self.create_slider_float(f, "Var. Densidade Atr.:", self.attractor_density_variation, 0, 80, current_row); current_row += 1
        self.create_slider(f, "Raio Inicial Anel:", self.initial_radius, 10, 200, current_row); current_row += 1
        self.create_slider(f, "Passo Expansão (Base):", self.radius_step_base, 5, 100, current_row); current_row += 1
        self.create_slider_float(f, "Irregularidade Anel:", self.ring_irregularity, 0, 100, current_row); current_row += 1
        self.create_slider_float(f, "Var. Expansão Anel:", self.expansion_variation, 0, 100, current_row); current_row += 1
        self.create_slider(f, "Escala Perlin:", self.perlin_scale, 10, 500, current_row); current_row += 1
        self.create_slider_float(f, "Força Perlin:", self.perlin_strength, 0, 150, current_row); current_row += 1
        self.create_slider(f, "Nº Lobos Cresc.:", self.num_growth_lobes, 0, 4, current_row); current_row += 1
        self.create_slider_float(f, "Mult. Atr. Lobos:", self.lobe_attractor_multiplier, 100, 300, current_row); current_row += 1
        self.create_slider(f, "Ângulo Espalh. Lobos (graus):", self.lobe_spread_angle, 10, 90, current_row); current_row += 1
        self.create_slider(f, "Movimento Lobos (graus):", self.lobe_movement_factor, 0, 30, current_row); current_row += 1
        self.create_slider(f, "Distância de Remoção:", self.kill_distance, 2, 30, current_row); current_row += 1
        self.create_slider(f, "Tamanho do Galho:", self.step_size, 1, 20, current_row); current_row += 1
        self.create_slider(f, "Intervalo de Frames:", self.frame_interval, 5, 100, current_row); current_row += 1
        self.create_slider(f, "Espessura da Linha:", self.line_thickness, 1, 10, current_row); current_row += 1
        
        ttk.Label(f, text="Cor do Fundo:").grid(row=current_row, column=0, sticky="w", pady=5); 
        self.bg_color_btn = tk.Button(f, text="Escolher", bg=self.bg_color, command=lambda: self.pick_color('bg')); self.bg_color_btn.grid(row=current_row, column=1, columnspan=2, sticky="ew"); current_row += 1
        
        ttk.Label(f, text="Cor do Galho:").grid(row=current_row, column=0, sticky="w", pady=5)
        self.branch_color_btn = tk.Button(f, text="Escolher", bg=self.branch_color, command=lambda: self.pick_color('branch')); self.branch_color_btn.grid(row=current_row, column=1, columnspan=2, sticky="ew"); current_row += 1
        
        ttk.Checkbutton(f, text="Fundo Transparente (WebM Alpha)", variable=self.transparent_bg, command=self.toggle_bg_color_button).grid(row=current_row, column=0, columnspan=3, sticky="w", pady=5); current_row += 1
        
        self.run_button = ttk.Button(f, text="Gerar Vídeo da Colônia...", command=self.start_generation); self.run_button.grid(row=current_row, column=0, columnspan=3, sticky="ew", pady=(10, 5)); current_row += 1
        self.progress_bar = ttk.Progressbar(f, orient='horizontal', mode='determinate'); self.progress_bar.grid(row=current_row, column=0, columnspan=3, sticky="ew", pady=5); current_row += 1
        
        log_frame = ttk.Frame(self.controls_frame); log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_box = tk.Text(log_frame, height=5, wrap=tk.WORD, state=tk.DISABLED, bg="#2b2b2b", fg="white", relief=tk.SOLID, borderwidth=1); self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_box.yview); scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.log_box['yscrollcommand'] = scrollbar.set
        self.toggle_bg_color_button()

    def create_slider(self, p, t, v, f, t_, r): ttk.Label(p, text=t).grid(row=r, column=0, sticky="w", pady=2); value_label = ttk.Label(p, text=f"{v.get():.0f}", width=4); value_label.grid(row=r, column=2, sticky="e", padx=5); slider = ttk.Scale(p, variable=v, from_=f, to=t_, orient='horizontal', command=lambda val: value_label.config(text=f"{float(val):.0f}")); slider.grid(row=r, column=1, sticky="ew")
    def create_slider_float(self, p, t, v, f, t_, r): ttk.Label(p, text=t).grid(row=r, column=0, sticky="w", pady=2); value_label = ttk.Label(p, text=f"{v.get()/100.0:.2f}", width=4); value_label.grid(row=r, column=2, sticky="e", padx=5); slider = ttk.Scale(p, variable=v, from_=f, to=t_, orient='horizontal', command=lambda val: value_label.config(text=f"{int(float(val))/100.0:.2f}")); slider.grid(row=r, column=1, sticky="ew")
    def log_message(self, m): self.log_box.config(state=tk.NORMAL); self.log_box.insert(tk.END, f"{m}\n"); self.log_box.see(tk.END); self.log_box.config(state=tk.DISABLED)
    def pick_color(self, t): c = colorchooser.askcolor(title=f"Escolha a cor para '{t}'")[1]; setattr(self, f"{t}_color", c); getattr(self, f"{t}_color_btn").config(bg=c)
    def toggle_bg_color_button(self):
        if self.transparent_bg.get(): self.bg_color_btn.config(state=tk.DISABLED, text="Transparente")
        else: self.bg_color_btn.config(state=tk.NORMAL, text="Escolher")

    def start_generation(self):
        filetypes = [("WebM Video (com Alpha)", "*.webm"), ("MP4 Video (sem Alpha)", "*.mp4"), ("Todos os arquivos", "*.*")]
        output_path = filedialog.asksaveasfilename(defaultextension=".webm" if self.transparent_bg.get() else ".mp4", filetypes=filetypes, title="Salvar vídeo como...")
        if not output_path: self.log_message("Geração cancelada."); return
        
        self.log_box.config(state=tk.NORMAL); self.log_box.delete('1.0', tk.END); self.log_box.config(state=tk.DISABLED)
        self.run_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.log_message("Iniciando geração da colônia...")

        params = {
            'max_nodes': self.max_nodes.get(),
            'attractors_per_ring_base': self.attractors_per_ring_base.get(),
            'attractor_density_variation': self.attractor_density_variation.get() / 100.0,
            'initial_radius': self.initial_radius.get(),
            'radius_step_base': self.radius_step_base.get(),
            'ring_irregularity': self.ring_irregularity.get() / 100.0,
            'expansion_variation': self.expansion_variation.get() / 100.0,
            'perlin_scale': self.perlin_scale.get(),
            'perlin_strength': self.perlin_strength.get() / 100.0,
            'num_growth_lobes': self.num_growth_lobes.get(),
            'lobe_attractor_multiplier': self.lobe_attractor_multiplier.get() / 100.0,
            'lobe_spread_angle': self.lobe_spread_angle.get() * math.pi / 180,
            'lobe_movement_factor': self.lobe_movement_factor.get(),
            'kill_distance': self.kill_distance.get(),
            'step_size': self.step_size.get(),
            'frame_interval': self.frame_interval.get(),
            'bg_color': self.bg_color,
            'branch_color': self.branch_color,
            'output_path': output_path,
            'width': 800, 'height': 800,
            'line_thickness': self.line_thickness.get(),
            'transparent_bg': self.transparent_bg.get()
        }
        
        self.generation_thread = threading.Thread(target=run_fractal_generation, args=(params, self.queue))
        self.generation_thread.start()
        self.master.after(100, self.check_queue)

    def check_queue(self):
        try:
            message = self.queue.get(block=False)
            if 'status' in message: self.log_message(message['status'])
            if 'progress' in message: self.progress_bar['value'] = message['progress']
            if 'preview_frame' in message: self.display_image(message['preview_frame'])
            if message.get('progress') == 100: self.run_button.config(state=tk.NORMAL); return
        except queue.Empty: pass
        
        if self.generation_thread.is_alive(): self.master.after(100, self.check_queue)
        else: self.run_button.config(state=tk.NORMAL)

    def display_image(self, img): self.master.after(50, lambda: self._update_image_display(img))
    def _update_image_display(self, img):
        w, h = img.size; frame_h = self.image_frame.winfo_height() - 20; frame_w = self.image_frame.winfo_width() - 20
        if frame_w <= 1 or frame_h <= 1: self.master.after(100, lambda: self._update_image_display(img)); return
        scale = min(frame_w / w, frame_h / h); new_w, new_h = int(w * scale), int(h * scale)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if img.mode == 'RGBA': self.tk_image = ImageTk.PhotoImage(img_resized)
        else: self.tk_image = ImageTk.PhotoImage(img_resized)
        self.image_label.config(image=self.tk_image, text="")

if __name__ == "__main__":
    root = tk.Tk()
    app = FractalApp(root)
    root.mainloop()
