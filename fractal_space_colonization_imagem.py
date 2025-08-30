import numpy as np
from PIL import Image, ImageDraw
import random
import time

# --- PARÂMETROS DE CONFIGURAÇÃO ---
IMG_WIDTH, IMG_HEIGHT = 800, 1000
NUM_ATTRACTORS = 3500           # Aumentei para mais detalhes na máscara
KILL_DISTANCE = 10
STEP_SIZE = 5
BG_COLOR = (10, 10, 20)
TREE_COLOR = (255, 255, 230)
STAGNATION_LIMIT = 10 

# =================== NOVO PARÂMETRO ===================
# Caminho para a sua imagem de máscara (em alto contraste, preto e branco)
# Certifique-se de que esta imagem está na mesma pasta do script, ou forneça o caminho completo.
MASK_IMAGE_PATH = 'mask_silhouette.png' 
# ======================================================

class Node:
    def __init__(self, pos, parent=None):
        self.pos = np.array(pos, dtype=float)
        self.parent = parent

def distance(p1, p2):
    return np.linalg.norm(p1 - p2)

# =================== NOVA FUNÇÃO ===================
def generate_attractors_from_mask(num, mask_path, target_width, target_height):
    """
    Gera pontos de atração baseados em uma imagem de máscara.
    Os pontos são gerados aleatoriamente dentro da área "ativa" da máscara (pixels pretos).
    A imagem da máscara é redimensionada para target_width x target_height.
    """
    print(f"Carregando máscara de: {mask_path}")
    try:
        mask_img = Image.open(mask_path).convert('L') # Carrega e converte para tons de cinza
        mask_img = mask_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    except FileNotFoundError:
        print(f"ERRO: Máscara '{mask_path}' não encontrada. Verifique o caminho do arquivo.")
        return []
    except Exception as e:
        print(f"ERRO ao carregar ou processar a máscara: {e}")
        return []

    # O algoritmo irá procurar pixels pretos (valor 0) como área válida
    # Se sua máscara for o inverso (silhueta branca em fundo preto), mude para `> 128` ou `== 255`
    mask_pixels = mask_img.load() 

    attractors = []
    attempts = 0
    max_attempts_multiplier = 5 # Tenta 5x mais pontos do que o necessário antes de desistir
    
    while len(attractors) < num and attempts < num * max_attempts_multiplier:
        x = random.randint(0, target_width - 1)
        y = random.randint(0, target_height - 1)
        
        # Verifica se o pixel na posição (x,y) da máscara é escuro (parte da silhueta)
        if mask_pixels[x, y] < 128: # Assumindo silhueta preta em fundo branco (valor < 128)
            attractors.append({'id': len(attractors), 'pos': np.array([x, y], dtype=float)})
        
        attempts += 1

    if len(attractors) < num:
        print(f"Aviso: Não foi possível gerar {num} atratores. Gerados {len(attractors)}.")
    else:
        print(f"Gerados {len(attractors)} atratores a partir da máscara.")
    
    return attractors
# ======================================================

def main():
    print("Iniciando a simulação com a lógica final de PODA POR ESTAGNAÇÃO e MÁSCARA...")
    start_time = time.time()

    # 1. INICIALIZAÇÃO
    # =================== MUDANÇA AQUI ===================
    attractors = generate_attractors_from_mask(NUM_ATTRACTORS, MASK_IMAGE_PATH, IMG_WIDTH, IMG_HEIGHT)
    if not attractors:
        print("Nenhum atrator gerado. Encerrando o script.")
        return
    # ======================================================

    root = Node([IMG_WIDTH / 2, IMG_HEIGHT]) # Posição da raiz (pode ser ajustada)
    nodes = [root]
    
    current = root
    for _ in range(5):
        new_node = Node([current.pos[0], current.pos[1] - STEP_SIZE], parent=current)
        nodes.append(new_node)
        current = new_node

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
            
            if closest_node_index == -1: # Se não encontrou nenhum nó (muito raro após inicialização)
                continue

            if stagnation_tracker[att_id]['closest_node_idx'] == closest_node_index:
                stagnation_tracker[att_id]['count'] += 1
            else:
                stagnation_tracker[att_id]['closest_node_idx'] = closest_node_index
                stagnation_tracker[att_id]['count'] = 1 
            
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

        # c. Poda (duas condições agora: estagnação e proximidade física)
        surviving_attractors = []
        removed_by_stagnation = 0
        removed_by_proximity = 0

        # Cria um conjunto dos IDs dos atratores que serão removidos
        ids_to_remove = set()

        for attractor in attractors:
            att_id = attractor['id']
            att_pos = attractor['pos']

            # Condição 1: Poda por estagnação
            if stagnation_tracker[att_id]['count'] >= STAGNATION_LIMIT:
                ids_to_remove.add(att_id)
                removed_by_stagnation += 1
                continue 

            # Condição 2: Poda por proximidade física (mais eficiente, checa apenas novos nós)
            is_killed_by_proximity = False
            for node in new_nodes: 
                if distance(att_pos, node.pos) < KILL_DISTANCE:
                    is_killed_by_proximity = True
                    break
            
            if is_killed_by_proximity:
                ids_to_remove.add(att_id)
                removed_by_proximity += 1
                continue

            # Se não foi removido por nenhuma das condições, adiciona aos sobreviventes
            surviving_attractors.append(attractor)
        
        attractors = surviving_attractors # Atualiza a lista de atratores
        
        # Limpa os dados do tracker para os atratores removidos
        for att_id in ids_to_remove:
            if att_id in stagnation_tracker:
                del stagnation_tracker[att_id]

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
            
    image.save('space_colonization_mask_fractal.png')
    end_time = time.time()
    print(f"Imagem 'space_colonization_mask_fractal.png' salva com sucesso!")
    print(f"Tempo total: {end_time - start_time:.2f} segundos.")


if __name__ == '__main__':
    main()
