# -*- coding: utf-8 -*-
# =============================================================================
#
#   Arquivo: space_colonization_final.py
#   Data: 30 de Agosto de 2025
#
#   Descrição:
#   Este script gera uma imagem de uma estrutura fractal que simula o
#   crescimento orgânico, como as nervuras de uma folha, raizes ou galhos
#   de uma árvore.
#
#   Algoritmo:
#   Implementação do "Space Colonization Algorithm". O crescimento ocorre de
#   forma iterativa, onde galhos se estendem em direção a uma nuvem de
#   pontos de atração. Para evitar loops infinitos causados por estagnação,
#   o script remove atratores que não demonstram progresso após um
#   certo número de iterações.
#
#   Dependências:
#   - Python 3
#   - NumPy
#   - Pillow
#   Para instalar: pip install numpy Pillow
#
# =============================================================================
# Desenvolvedores: Julie Pires, Marcelo Ribeiro, Francisco Freitas, Angélica de
#                   Carvalho
#
# Parte do projeto para o evento #24.ART - Encontro Internacional de Arte e
#                                   Tecnologia / Exposição EmMeio#17
#
# Nome da Obra: Existência Híbrida: (des)dobrando corpos numa anatomia gráfica 
#                                   em Realidade Aumentada
# =============================================================================
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
import numpy as np
from PIL import Image, ImageDraw, ImageTk
import random
import time
import threading
import queue

# =============================================================================
# NÚCLEO DO ALGORITMO DE GERAÇÃO DO FRACTAL (sem alterações)
# =============================================================================
def run_fractal_generation(params, output_queue):
    try:
        # 1. INICIALIZAÇÃO E GERAÇÃO DE ATRATORES
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

        # 2. INICIALIZAÇÃO DA ÁRVORE
        root_pos_x = params.get('root_x', params['width'] / 2)
        root_pos_y = params.get('root_y', params['height'])
        root = {'pos': np.array([root_pos_x, root_pos_y], dtype=float), 'parent': None}
        nodes = [root]
        current = root
        for _ in range(5):
            new_node = {'pos': np.array([current['pos'][0], current['pos'][1] - params['step_size']], dtype=float), 'parent': current}
            nodes.append(new_node)
            current = new_node

        stagnation_tracker = {att['id']: {'closest_node_idx': -1, 'count': 0} for att in attractors}
        initial_attractors = len(attractors)

        # 3. PROCESSO DE CRESCIMENTO (LOOP PRINCIPAL)
        iterations = 0
        while attractors:
            iterations += 1
            
            growth_vectors = {i: [] for i in range(len(nodes))}
            for attractor in attractors:
                att_pos = attractor['pos']
                att_id = attractor['id']
                closest_node_index = -1
                min_dist = float('inf')
                for i, node in enumerate(nodes):
                    d = np.linalg.norm(att_pos - node['pos'])
                    if d < min_dist:
                        min_dist = d
                        closest_node_index = i
                
                if stagnation_tracker[att_id]['closest_node_idx'] == closest_node_index:
                    stagnation_tracker[att_id]['count'] += 1
                else:
                    stagnation_tracker[att_id]['closest_node_idx'] = closest_node_index
                    stagnation_tracker[att_id]['count'] = 1
                
                direction = att_pos - nodes[closest_node_index]['pos']
                norm = np.linalg.norm(direction)
                if norm > 0:
                    growth_vectors[closest_node_index].append(direction / norm)
            
            new_nodes = []
            for node_index, vectors in growth_vectors.items():
                if vectors:
                    avg_direction = np.mean(vectors, axis=0)
                    norm = np.linalg.norm(avg_direction)
                    if norm > 0:
                        avg_direction /= norm
                        parent_node = nodes[node_index]
                        new_pos = parent_node['pos'] + avg_direction * params['step_size']
                        new_node = {'pos': new_pos, 'parent': parent_node}
                        new_nodes.append(new_node)
            nodes.extend(new_nodes)
            
            # Poda
            ids_to_remove = set()
            removed_by_proximity = 0
            removed_by_stagnation = 0
            for attractor in attractors:
                att_id = attractor['id']
                att_pos = attractor['pos']
                if stagnation_tracker[att_id]['count'] >= params['stagnation_limit']:
                    ids_to_remove.add(att_id)
                    removed_by_stagnation += 1
                    continue
                
                is_killed_by_proximity = False
                for node in nodes:
                    if np.linalg.norm(att_pos - node['pos']) < params['kill_distance']:
                        is_killed_by_proximity = True
                        break

                if is_killed_by_proximity:
                    ids_to_remove.add(att_id)
                    removed_by_proximity += 1
                    continue

            if ids_to_remove:
                attractors = [att for att in attractors if att['id'] not in ids_to_remove]
                for att_id in ids_to_remove:
                    if att_id in stagnation_tracker: del stagnation_tracker[att_id]

            if iterations % 5 == 0 or not attractors or ids_to_remove:
                progress = 100 * (initial_attractors - len(attractors)) / initial_attractors
                status_text = f"Iteração {iterations}: {len(attractors)} atratores restantes..."
                if removed_by_stagnation > 0 or removed_by_proximity > 0:
                    status_text += f" (Removidos: {removed_by_proximity} prox, {removed_by_stagnation} estag)"
                output_queue.put({'status': status_text, 'progress': progress})

        # 4. DESENHO DA IMAGEM FINAL
        output_queue.put({'status': 'Renderizando imagem final...', 'progress': 99})
        image = Image.new('RGB', (params['width'], params['height']), params['bg_color'])
        draw = ImageDraw.Draw(image)
        for node in nodes:
            if node['parent']:
                p1 = node['parent']['pos']
                p2 = node['pos']
                draw.line((p1[0], p1[1], p2[0], p2[1]), fill=params['tree_color'], width=1)
        
        output_queue.put({'status': 'Concluído!', 'progress': 100, 'image': image})

    except Exception as e:
        output_queue.put({'status': f'Erro: {e}', 'progress': 100})

# =============================================================================
# CLASSE DA APLICAÇÃO TKINTER (GUI)
# =============================================================================
class FractalApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Gerador de Fractal Orgânico - Grupo: Imagem(i)Materia")
        self.master.geometry("1200x800")

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.mask_path = tk.StringVar(value="")
        self.num_attractors = tk.IntVar(value=1500)
        self.kill_distance = tk.IntVar(value=10)
        self.step_size = tk.IntVar(value=5)
        self.stagnation_limit = tk.IntVar(value=10)
        self.bg_color = '#0a0a14'
        self.tree_color = '#ffffd0'
        
        # =================== MUDANÇA: ARMAZENAR A IMAGEM GERADA ===================
        self.generated_image = None
        # ========================================================================

        self.generation_thread = None
        self.queue = queue.Queue()

        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.controls_frame = ttk.LabelFrame(self.main_frame, text="Controles", padding="10", width=300)
        self.controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.controls_frame.pack_propagate(False)

        self.image_frame = ttk.LabelFrame(self.main_frame, text="Resultado", padding="10")
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.image_label = ttk.Label(self.image_frame, text="A imagem gerada aparecerá aqui.", anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)

        self.create_controls()

    def create_controls(self):
        controls_inner_frame = ttk.Frame(self.controls_frame)
        controls_inner_frame.pack(fill=tk.X, expand=True)

        ttk.Button(controls_inner_frame, text="Selecionar Imagem de Máscara", command=self.select_file).grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        self.file_label = ttk.Label(controls_inner_frame, text="Nenhum arquivo selecionado.", wraplength=280)
        self.file_label.grid(row=1, column=0, columnspan=2, pady=5)

        self.create_slider(controls_inner_frame, "Nº de Atratores:", self.num_attractors, 200, 5000, 2)
        self.create_slider(controls_inner_frame, "Distância de Remoção:", self.kill_distance, 2, 30, 3)
        self.create_slider(controls_inner_frame, "Tamanho do Passo:", self.step_size, 1, 20, 4)
        self.create_slider(controls_inner_frame, "Limite de Estagnação:", self.stagnation_limit, 5, 50, 5)

        ttk.Label(controls_inner_frame, text="Cor do Fundo:").grid(row=6, column=0, sticky="w", pady=10)
        self.bg_color_btn = tk.Button(controls_inner_frame, text="Escolher", bg=self.bg_color, command=lambda: self.pick_color('bg'))
        self.bg_color_btn.grid(row=6, column=1, sticky="ew")

        ttk.Label(controls_inner_frame, text="Cor da Árvore:").grid(row=7, column=0, sticky="w", pady=5)
        self.tree_color_btn = tk.Button(controls_inner_frame, text="Escolher", bg=self.tree_color, command=lambda: self.pick_color('tree'))
        self.tree_color_btn.grid(row=7, column=1, sticky="ew")

        self.run_button = ttk.Button(controls_inner_frame, text="Gerar Fractal", command=self.start_generation)
        self.run_button.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(20, 5))
        
        # =================== MUDANÇA: NOVO BOTÃO DE SALVAR ===================
        self.save_button = ttk.Button(controls_inner_frame, text="Salvar Imagem...", command=self.save_image, state=tk.DISABLED)
        self.save_button.grid(row=9, column=0, columnspan=2, sticky="ew", pady=5)
        # ========================================================================

        self.progress_bar = ttk.Progressbar(controls_inner_frame, orient='horizontal', mode='determinate')
        self.progress_bar.grid(row=10, column=0, columnspan=2, sticky="ew", pady=5)
        
        log_frame = ttk.Frame(self.controls_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.log_box = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, bg="#2b2b2b", fg="white", relief=tk.SOLID, borderwidth=1)
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_box.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box['yscrollcommand'] = scrollbar.set

    def create_slider(self, parent, text, variable, from_, to, row):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Scale(parent, variable=variable, from_=from_, to=to, orient='horizontal').grid(row=row, column=1, sticky="ew")

    def log_message(self, message):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, f"{message}\n")
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp"), ("Todos os arquivos", "*.*")])
        if path:
            self.mask_path.set(path)
            self.file_label.config(text=path.split('/')[-1])

    def pick_color(self, target):
        color_code = colorchooser.askcolor(title=f"Escolha a cor para '{target}'")[1]
        if color_code:
            if target == 'bg':
                self.bg_color = color_code
                self.bg_color_btn.config(bg=color_code)
            elif target == 'tree':
                self.tree_color = color_code
                self.tree_color_btn.config(bg=color_code)

    def start_generation(self):
        if not self.mask_path.get():
            self.log_message("Erro: Por favor, selecione uma imagem de máscara primeiro.")
            return

        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete('1.0', tk.END)
        self.log_box.config(state=tk.DISABLED)
        
        # =================== MUDANÇA: DESABILITAR BOTÃO DE SALVAR ===================
        self.save_button.config(state=tk.DISABLED)
        self.generated_image = None
        # ===========================================================================

        self.run_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.log_message("Iniciando geração...")

        params = {
            'mask_path': self.mask_path.get(),
            'num_attractors': self.num_attractors.get(),
            'kill_distance': self.kill_distance.get(),
            'step_size': self.step_size.get(),
            'stagnation_limit': self.stagnation_limit.get(),
            'bg_color': self.bg_color,
            'tree_color': self.tree_color,
            'width': 800,
            'height': 1000
        }
        
        self.generation_thread = threading.Thread(target=run_fractal_generation, args=(params, self.queue))
        self.generation_thread.start()
        self.master.after(100, self.check_queue)

    def check_queue(self):
        try:
            message = self.queue.get(block=False)
            if 'status' in message: self.log_message(message['status'])
            if 'progress' in message: self.progress_bar['value'] = message['progress']
            if 'image' in message:
                self.generated_image = message['image'] # Armazena a imagem
                self.display_image(self.generated_image)
                self.run_button.config(state=tk.NORMAL)
                self.save_button.config(state=tk.NORMAL) # Habilita o botão de salvar
                self.log_message("--- Fim da Execução ---")
                return 
        except queue.Empty:
            pass
        
        if self.generation_thread.is_alive() or not self.queue.empty():
            self.master.after(100, self.check_queue)
        else:
            self.run_button.config(state=tk.NORMAL)

    # =================== MUDANÇA: NOVA FUNÇÃO PARA SALVAR A IMAGEM ===================
    def save_image(self):
        if self.generated_image is None:
            self.log_message("Nenhuma imagem gerada para salvar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            title="Salvar imagem como..."
        )

        if filepath:
            try:
                self.generated_image.save(filepath)
                self.log_message(f"Imagem salva com sucesso em:\n{filepath}")
            except Exception as e:
                self.log_message(f"Erro ao salvar a imagem: {e}")
    # ==============================================================================

    def display_image(self, img):
        self.master.after(50, lambda: self._update_image_display(img))

    def _update_image_display(self, img):
        w, h = img.size
        frame_h = self.image_frame.winfo_height() - 20
        frame_w = self.image_frame.winfo_width() - 20
        
        if frame_w <= 1 or frame_h <= 1:
            self.master.after(100, lambda: self._update_image_display(img))
            return
            
        scale = min(frame_w / w, frame_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        self.tk_image = ImageTk.PhotoImage(img_resized)
        self.image_label.config(image=self.tk_image, text="")

# =============================================================================
# PONTO DE ENTRADA PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = FractalApp(root)
    root.mainloop()
