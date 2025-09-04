# -*- coding: utf-8 -*-
# =============================================================================
#
#   Arquivo: space_colonization_video_generator.py (v3, dimensões corrigidas)
#
#   Descrição:
#   Este script gera um vídeo (MP4) da animação de crescimento de uma
#   estrutura fractal usando o "Space Colonization Algorithm".
#
#   Dependências:
#   - Python 3
#   - NumPy
#   - Pillow
#   - imageio (com ffmpeg)
#   Para instalar: pip install numpy Pillow "imageio[ffmpeg]"
#
# =============================================================================
# Desenvolvedores: Julie Pires, Marcelo Ribeiro, Francisco Freitas, Angélica de
#                   Carvalho
# (e contribuições da IA)
# =============================================================================
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
import numpy as np
from PIL import Image, ImageDraw, ImageTk
import random
import time
import threading
import queue
# =================== MUDANÇA 1: IMPORTAÇÃO CORRIGIDA ===================
import imageio.v2 as imageio
# =====================================================================
import os
import tempfile
import shutil

# =============================================================================
# NÚCLEO DO ALGORITMO DE GERAÇÃO DO FRACTAL E VÍDEO
# =============================================================================
def run_fractal_generation(params, output_queue):
    frame_folder = tempfile.mkdtemp()
    frame_files = []
    
    try:
        output_queue.put({'status': 'Carregando máscara e gerando atratores...'})
        
        mask_img = Image.open(params['mask_path']).convert('L')
        mask_img = mask_img.resize((params['width'], params['height']), Image.Resampling.LANCZOS)
        mask_pixels = mask_img.load()

        attractors = []
        while len(attractors) < params['num_attractors']:
            x = random.randint(0, params['width'] - 1)
            y = random.randint(0, params['height'] - 1)
            if mask_pixels[x, y] < 128:
                attractors.append({'id': len(attractors), 'pos': np.array([x, y], dtype=float)})
        
        if not attractors:
            output_queue.put({'status': 'Erro: Nenhum atrator gerado a partir da máscara.', 'progress': 100})
            return

        root = {'pos': np.array([params['width'] / 2, params['height']], dtype=float), 'parent': None}
        nodes = [root]
        current = root
        for _ in range(5):
            new_node = {'pos': np.array([current['pos'][0], current['pos'][1] - params['step_size']], dtype=float), 'parent': current}
            nodes.append(new_node)
            current = new_node

        stagnation_tracker = {att['id']: {'closest_node_idx': -1, 'count': 0} for att in attractors}
        initial_attractors = len(attractors)

        iterations = 0
        while attractors:
            iterations += 1
            
            growth_vectors = {i: [] for i in range(len(nodes))}
            for attractor in attractors:
                att_pos = attractor['pos']; att_id = attractor['id']
                closest_node_index = -1; min_dist = float('inf')
                for i, node in enumerate(nodes):
                    d = np.linalg.norm(att_pos - node['pos'])
                    if d < min_dist: min_dist = d; closest_node_index = i
                if stagnation_tracker[att_id]['closest_node_idx'] == closest_node_index:
                    stagnation_tracker[att_id]['count'] += 1
                else:
                    stagnation_tracker[att_id]['closest_node_idx'] = closest_node_index; stagnation_tracker[att_id]['count'] = 1
                direction = att_pos - nodes[closest_node_index]['pos']; norm = np.linalg.norm(direction)
                if norm > 0: growth_vectors[closest_node_index].append(direction / norm)
            
            new_nodes = []
            for node_index, vectors in growth_vectors.items():
                if vectors:
                    avg_direction = np.mean(vectors, axis=0); norm = np.linalg.norm(avg_direction)
                    if norm > 0:
                        avg_direction /= norm; parent_node = nodes[node_index]
                        new_pos = parent_node['pos'] + avg_direction * params['step_size']
                        new_node = {'pos': new_pos, 'parent': parent_node}; new_nodes.append(new_node)
            nodes.extend(new_nodes)
            
            ids_to_remove = set()
            for attractor in attractors:
                att_id = attractor['id']; att_pos = attractor['pos']
                if stagnation_tracker[att_id]['count'] >= params['stagnation_limit']: ids_to_remove.add(att_id); continue
                for node in nodes:
                    if np.linalg.norm(att_pos - node['pos']) < params['kill_distance']: ids_to_remove.add(att_id); break
            
            if ids_to_remove:
                attractors = [att for att in attractors if att['id'] not in ids_to_remove]
                for att_id in ids_to_remove:
                    if att_id in stagnation_tracker: del stagnation_tracker[att_id]

            progress = 100 * (initial_attractors - len(attractors)) / initial_attractors
            status_text = f"Iteração {iterations}: {len(attractors)} atratores restantes..."
            output_queue.put({'status': status_text, 'progress': progress})

            if iterations % params['frame_interval'] == 0 or not attractors:
                frame_image = Image.new('RGB', (params['width'], params['height']), params['bg_color'])
                draw = ImageDraw.Draw(frame_image)
                for node in nodes:
                    if node['parent']:
                        p1 = node['parent']['pos']; p2 = node['pos']
                        draw.line((p1[0], p1[1], p2[0], p2[1]), fill=params['tree_color'], width=params['line_width'])
                
                frame_path = os.path.join(frame_folder, f"frame_{len(frame_files):05d}.png")
                frame_image.save(frame_path)
                frame_files.append(frame_path)
                
                output_queue.put({'preview_frame': frame_image})

        output_queue.put({'status': f'Crescimento concluído. Montando vídeo com {len(frame_files)} frames...'})
        
        with imageio.get_writer(params['output_path'], fps=30, macro_block_size=None) as writer:
            for filename in frame_files:
                image = imageio.imread(filename)
                writer.append_data(image)

        output_queue.put({'status': f'Concluído! Vídeo salvo em:\n{params["output_path"]}', 'progress': 100})

    except Exception as e:
        output_queue.put({'status': f'Erro: {e}', 'progress': 100})
    finally:
        shutil.rmtree(frame_folder)


# =============================================================================
# CLASSE DA APLICAÇÃO TKINTER (GUI)
# =============================================================================
class FractalApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Gerador de Fractal Orgânico - Grupo: Imagem(i)Materia")
        self.master.geometry("1200x800")
        self.style = ttk.Style(); self.style.theme_use('clam')

        self.mask_path = tk.StringVar(value="")
        self.num_attractors = tk.IntVar(value=1500)
        self.kill_distance = tk.IntVar(value=10)
        self.step_size = tk.IntVar(value=5)
        self.stagnation_limit = tk.IntVar(value=10)
        self.line_width = tk.IntVar(value=1)
        self.frame_interval = tk.IntVar(value=5)
        self.bg_color = '#0a0a14'
        self.tree_color = '#ffffd0'
        
        self.generated_image = None
        self.generation_thread = None
        self.queue = queue.Queue()

        self.main_frame = ttk.Frame(self.master, padding="10"); self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.controls_frame = ttk.LabelFrame(self.main_frame, text="Controles", padding="10", width=350); self.controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10)); self.controls_frame.pack_propagate(False)
        self.image_frame = ttk.LabelFrame(self.main_frame, text="Pré-visualização", padding="10"); self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.image_label = ttk.Label(self.image_frame, text="A pré-visualização do crescimento aparecerá aqui.", anchor=tk.CENTER); self.image_label.pack(fill=tk.BOTH, expand=True)
        self.create_controls()

    def create_controls(self):
        f = ttk.Frame(self.controls_frame); f.pack(fill=tk.X, expand=True)
        f.columnconfigure(1, weight=1)
        ttk.Button(f, text="Selecionar Imagem de Máscara", command=self.select_file).grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        self.file_label = ttk.Label(f, text="Nenhum arquivo selecionado.", wraplength=320); self.file_label.grid(row=1, column=0, columnspan=3, pady=5)
        self.create_slider(f, "Nº de Atratores:", self.num_attractors, 200, 5000, 2)
        self.create_slider(f, "Distância de Remoção:", self.kill_distance, 2, 30, 3)
        self.create_slider(f, "Tamanho do Passo:", self.step_size, 1, 20, 4)
        self.create_slider(f, "Limite de Estagnação:", self.stagnation_limit, 5, 50, 5)
        self.create_slider(f, "Espessura da Linha:", self.line_width, 1, 10, 6)
        self.create_slider(f, "Intervalo de Frames:", self.frame_interval, 1, 50, 7)
        ttk.Label(f, text="Cor do Fundo:").grid(row=8, column=0, sticky="w", pady=10)
        self.bg_color_btn = tk.Button(f, text="Escolher", bg=self.bg_color, command=lambda: self.pick_color('bg')); self.bg_color_btn.grid(row=8, column=1, columnspan=2, sticky="ew")
        ttk.Label(f, text="Cor da Árvore:").grid(row=9, column=0, sticky="w", pady=5)
        self.tree_color_btn = tk.Button(f, text="Escolher", bg=self.tree_color, command=lambda: self.pick_color('tree')); self.tree_color_btn.grid(row=9, column=1, columnspan=2, sticky="ew")
        self.run_button = ttk.Button(f, text="Gerar Vídeo...", command=self.start_generation); self.run_button.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(20, 5))
        self.progress_bar = ttk.Progressbar(f, orient='horizontal', mode='determinate'); self.progress_bar.grid(row=11, column=0, columnspan=3, sticky="ew", pady=5)
        log_frame = ttk.Frame(self.controls_frame); log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_box = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, bg="#2b2b2b", fg="white", relief=tk.SOLID, borderwidth=1); self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_box.yview); scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.log_box['yscrollcommand'] = scrollbar.set

    def create_slider(self, p, t, v, f, t_, r): ttk.Label(p, text=t).grid(row=r, column=0, sticky="w", pady=5); value_label = ttk.Label(p, text=f"{v.get():.0f}", width=4); value_label.grid(row=r, column=2, sticky="e", padx=5); slider = ttk.Scale(p, variable=v, from_=f, to=t_, orient='horizontal', command=lambda val: value_label.config(text=f"{float(val):.0f}")); slider.grid(row=r, column=1, sticky="ew")
    def log_message(self, m): self.log_box.config(state=tk.NORMAL); self.log_box.insert(tk.END, f"{m}\n"); self.log_box.see(tk.END); self.log_box.config(state=tk.DISABLED)
    def select_file(self): path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp"),("Todos", "*.*")]); self.mask_path.set(path); self.file_label.config(text=path.split('/')[-1])
    def pick_color(self, t): c = colorchooser.askcolor(title=f"Escolha a cor para '{t}'")[1]; setattr(self, f"{t}_color", c); getattr(self, f"{t}_color_btn").config(bg=c)

    def start_generation(self):
        if not self.mask_path.get(): self.log_message("Erro: Selecione uma imagem de máscara."); return
        output_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")], title="Salvar vídeo como...")
        if not output_path: self.log_message("Geração cancelada."); return
        self.log_box.config(state=tk.NORMAL); self.log_box.delete('1.0', tk.END); self.log_box.config(state=tk.DISABLED)
        self.run_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.log_message("Iniciando geração...")

        params = {
            'mask_path': self.mask_path.get(), 'num_attractors': self.num_attractors.get(),
            'kill_distance': self.kill_distance.get(), 'step_size': self.step_size.get(),
            'stagnation_limit': self.stagnation_limit.get(), 'bg_color': self.bg_color,
            'tree_color': self.tree_color, 'line_width': self.line_width.get(),
            'frame_interval': self.frame_interval.get(), 'output_path': output_path,
            # =================== MUDANÇA 2: DIMENSÃO CORRIGIDA ===================
            'width': 800, 'height': 1008
            # =====================================================================
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
        self.tk_image = ImageTk.PhotoImage(img_resized); self.image_label.config(image=self.tk_image, text="")

# =============================================================================
# PONTO DE ENTRADA PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = FractalApp(root)
    root.mainloop()
