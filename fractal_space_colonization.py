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
import numpy as np
from PIL import Image, ImageDraw
import random
import time

# --- PARÂMETROS DE CONFIGURAÇÃO ---
IMG_WIDTH, IMG_HEIGHT = 800, 1000
NUM_ATTRACTORS = 700
KILL_DISTANCE = 10  # Distância de "morte" por proximidade física (ainda útil)
STEP_SIZE = 5
BG_COLOR = (10, 10, 20)
TREE_COLOR = (255, 255, 230)

# =================== NOVO PARÂMETRO ===================
# Se um atrator não fizer progresso por este número de iterações, ele é removido.
STAGNATION_LIMIT = 10 
# ======================================================

class Node:
    def __init__(self, pos, parent=None):
        self.pos = np.array(pos, dtype=float)
        self.parent = parent

def generate_leaf_shaped_attractors(num, width, height):
    attractors = []
    center_x, center_y = width / 2, height / 2
    radius_x, radius_y = width / 2 - 50, height / 2 - 50
    
    while len(attractors) < num:
        x = random.uniform(0, width)
        y = random.uniform(0, height)
        if ((x - center_x)**2 / radius_x**2) + ((y - center_y)**2 / radius_y**2) <= 1:
            # Damos a cada atrator um ID único para rastreamento
            attractors.append({'id': len(attractors), 'pos': np.array([x, y])})
    return attractors

def distance(p1, p2):
    return np.linalg.norm(p1 - p2)

def main():
    print("Iniciando a simulação com a lógica final de PODA POR ESTAGNAÇÃO...")
    start_time = time.time()

    # 1. INICIALIZAÇÃO
    attractors = generate_leaf_shaped_attractors(NUM_ATTRACTORS, IMG_WIDTH, IMG_HEIGHT)
    root = Node([IMG_WIDTH / 2, IMG_HEIGHT])
    nodes = [root]
    
    current = root
    for _ in range(5):
        new_node = Node([current.pos[0], current.pos[1] - STEP_SIZE], parent=current)
        nodes.append(new_node)
        current = new_node

    # Dicionário para rastrear a estagnação de cada atrator
    stagnation_tracker = {att['id']: {'closest_node_idx': -1, 'count': 0} for att in attractors}

    # 2. PROCESSO DE CRESCIMENTO (LOOP PRINCIPAL)
    iterations = 0
    while attractors:
        iterations += 1
        
        # a. Associação e rastreamento de estagnação
        growth_vectors = {i: [] for i in range(len(nodes))}
        for attractor in attractors:
            att_pos = attractor['pos']
            att_id = attractor['id']

            closest_node_index = -1
            min_dist = float('inf')
            for i, node in enumerate(nodes):
                d = distance(att_pos, node.pos)
                if d < min_dist:
                    min_dist = d
                    closest_node_index = i
            
            # Atualiza o rastreador de estagnação
            if stagnation_tracker[att_id]['closest_node_idx'] == closest_node_index:
                stagnation_tracker[att_id]['count'] += 1
            else:
                stagnation_tracker[att_id]['closest_node_idx'] = closest_node_index
                stagnation_tracker[att_id]['count'] = 1 # Reseta a contagem
            
            direction = att_pos - nodes[closest_node_index].pos
            norm = np.linalg.norm(direction)
            if norm > 0:
                growth_vectors[closest_node_index].append(direction / norm)

        # b. Crescimento
        new_nodes = []
        for node_index, vectors in growth_vectors.items():
            if vectors:
                avg_direction = np.mean(vectors, axis=0)
                norm = np.linalg.norm(avg_direction)
                if norm > 0:
                    avg_direction /= norm
                    parent_node = nodes[node_index]
                    new_pos = parent_node.pos + avg_direction * STEP_SIZE
                    new_node = Node(new_pos, parent=parent_node)
                    new_nodes.append(new_node)
        
        nodes.extend(new_nodes)

        # c. Poda (duas condições agora)
        surviving_attractors = []
        removed_by_stagnation = 0
        removed_by_proximity = 0

        for attractor in attractors:
            att_id = attractor['id']
            att_pos = attractor['pos']

            # Condição 1: Poda por estagnação
            if stagnation_tracker[att_id]['count'] >= STAGNATION_LIMIT:
                removed_by_stagnation += 1
                continue # Pula para o próximo atrator, removendo o atual

            # Condição 2: Poda por proximidade física
            is_killed_by_proximity = False
            for node in new_nodes: # Checa apenas contra os nós novos (otimização)
                if distance(att_pos, node.pos) < KILL_DISTANCE:
                    is_killed_by_proximity = True
                    break
            
            if is_killed_by_proximity:
                removed_by_proximity += 1
                continue

            surviving_attractors.append(attractor)
        
        attractors = surviving_attractors
        
        if iterations % 10 == 0 or not attractors:
            print(f"Iteração {iterations}: {len(attractors)} atratores restantes. "
                  f"(Removidos nesta rodada: {removed_by_proximity} por proximidade, "
                  f"{removed_by_stagnation} por estagnação)")

    print("Processo de crescimento finalizado.")

    # 3. DESENHAR A IMAGEM
    print("Desenhando a imagem final...")
    image = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(image)

    for node in nodes:
        if node.parent:
            draw.line(
                (node.parent.pos[0], node.parent.pos[1], node.pos[0], node.pos[1]),
                fill=TREE_COLOR,
                width=1
            )
            
    image.save('space_colonization_final_garantido.png')
    end_time = time.time()
    print(f"Imagem 'space_colonization_final_garantido.png' salva com sucesso!")
    print(f"Tempo total: {end_time - start_time:.2f} segundos.")


if __name__ == '__main__':
    main()
