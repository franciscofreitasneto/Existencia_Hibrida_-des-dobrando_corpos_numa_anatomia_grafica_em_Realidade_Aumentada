# -*- coding: utf-8 -*-
# =============================================================================
#
#   Arquivo: Fractal3d.py (versão final com processamento explícito)
#
# =============================================================================
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
import trimesh
import argparse
import time

def export_tree_to_obj(nodes, filename):
    """Exporta a árvore de nós (vértices e arestas) para um arquivo .obj."""
    print(f"Exportando {len(nodes)} nós para {filename}...")
    
    node_to_index = {id(node): i + 1 for i, node in enumerate(nodes)}

    with open(filename, 'w') as f:
        f.write("# Fractal 3D Gerado com Space Colonization\n")
        
        for node in nodes:
            pos = node['pos']
            f.write(f"v {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}\n")
            
        for node in nodes:
            if node['parent']:
                parent_idx = node_to_index[id(node['parent'])]
                child_idx = node_to_index[id(node)]
                f.write(f"l {parent_idx} {child_idx}\n")
    print("Exportação concluída.")

def run_fractal_generation_3d(params):
    """Executa o algoritmo de colonização do espaço em 3D."""
    
    # 1. CARREGAR MALHA E GERAR ATRATORES
    print(f"Carregando malha de '{params['input_file']}'...")
    try:
        mesh = trimesh.load_mesh(params['input_file'])
        
        # =================== CORREÇÃO FINAL: PROCESSAMENTO EXPLÍCITO ===================
        # Força o trimesh a calcular todas as propriedades da malha, incluindo o volume.
        # Esta linha é a nossa principal tentativa para resolver o erro de volume zero.
        mesh.process()
        # ============================================================================

        if not mesh.is_watertight:
            print("Aviso: A malha não é 'watertight'. Tentando consertar...")
            mesh.fill_holes()
            if not mesh.is_watertight:
                 print("Aviso: A correção automática falhou. O resultado pode ser impreciso.")
        
        if mesh.volume is None or mesh.volume <= 1e-6:
            print(f"\nERRO CRÍTICO: A malha tem volume inválido ({mesh.volume}).")
            print("Isso acontece se a malha não for um volume fechado ('watertight').")
            print("POR FAVOR, tente consertar o seu modelo 3D no Blender antes de usar.")
            return None

        print(f"Gerando {params['num_attractors']} atratores dentro do volume da malha (Volume: {mesh.volume:.2f})...")
        
        pitch = (mesh.volume / params['num_attractors'])**(1/3) * 0.5
        print(f"Usando um pitch de voxel de {pitch:.4f}...")
        
        voxelized_mesh = mesh.voxelized(pitch=pitch)
        
        # O VoxelGrid não tem o método 'sample'. Usamos '.points' para pegar o centro de cada voxel preenchido.
        all_voxel_points = voxelized_mesh.points
        
        if len(all_voxel_points) == 0:
            print("ERRO: A voxelização não resultou em nenhum ponto. Tente um pitch maior ou verifique a malha.")
            return None

        # Seleciona uma amostra aleatória dos pontos dos voxels
        if len(all_voxel_points) > params['num_attractors']:
             indices = np.random.choice(len(all_voxel_points), size=params['num_attractors'], replace=False)
             attractor_points = all_voxel_points[indices]
        else:
             attractor_points = all_voxel_points


        attractors = [{'id': i, 'pos': p} for i, p in enumerate(attractor_points)]
        print(f"{len(attractors)} atratores gerados com sucesso.")
    except Exception as e:
        print(f"Erro ao carregar a malha ou gerar atratores: {e}")
        import traceback
        traceback.print_exc()
        return None

    # 2. INICIALIZAÇÃO DA ÁRVORE
    min_point = mesh.bounds[0]
    root_pos = np.array([ (mesh.bounds[0][0] + mesh.bounds[1][0]) / 2, 
                          (mesh.bounds[0][1] + mesh.bounds[1][1]) / 2, 
                          min_point[2] ])
    
    root = {'pos': root_pos, 'parent': None}
    nodes = [root]
    current = root
    for _ in range(5):
        new_pos = np.copy(current['pos'])
        new_pos[2] += params['step_size']
        new_node = {'pos': new_pos, 'parent': current}
        nodes.append(new_node)
        current = new_node

    stagnation_tracker = {att['id']: {'closest_node_idx': -1, 'count': 0} for att in attractors}
    initial_attractors = len(attractors)

    # 3. PROCESSO DE CRESCIMENTO
    start_time = time.time()
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
        
        ids_to_remove = set()
        for attractor in attractors:
            att_id = attractor['id']
            att_pos = attractor['pos']
            if stagnation_tracker[att_id]['count'] >= params['stagnation_limit']:
                ids_to_remove.add(att_id)
                continue
            for node in nodes:
                if np.linalg.norm(att_pos - node['pos']) < params['kill_distance']:
                    ids_to_remove.add(att_id)
                    break
        
        if ids_to_remove:
            attractors = [att for att in attractors if att['id'] not in ids_to_remove]
            for att_id in ids_to_remove:
                if att_id in stagnation_tracker: del stagnation_tracker[att_id]

        if iterations % 10 == 0 or not attractors:
            progress = 100 * (initial_attractors - len(attractors)) / initial_attractors
            print(f"Iteração {iterations}: {len(attractors)} atratores restantes ({progress:.1f}%)")

    end_time = time.time()
    print(f"Processo de crescimento finalizado em {end_time - start_time:.2f} segundos.")
    return nodes

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera um fractal 3D dentro de uma malha.")
    parser.add_argument("input_file", help="Caminho para o arquivo de malha de entrada (.obj, .stl, etc.)")
    parser.add_argument("output_file", help="Caminho para o arquivo de saída .obj")
    parser.add_argument("--pontos", type=int, default=5000, help="Número de pontos de atração a serem gerados.")
    parser.add_argument("--passo", type=float, default=0.5, help="Tamanho do passo de crescimento dos galhos.")
    parser.add_argument("--dist_remocao", type=float, default=2.0, help="Distância para um galho remover um atrator.")
    parser.add_argument("--estagnacao", type=int, default=15, help="Limite de iterações para remover um atrator estagnado.")
    
    args = parser.parse_args()

    params = {
        'input_file': args.input_file,
        'num_attractors': args.pontos,
        'step_size': args.passo,
        'kill_distance': args.dist_remocao,
        'stagnation_limit': args.estagnacao
    }

    final_nodes = run_fractal_generation_3d(params)

    if final_nodes:
        export_tree_to_obj(final_nodes, args.output_file)
