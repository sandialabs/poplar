import parsl
from parsl import python_app, bash_app, join_app
import argparse
import os
from os import system
import glob
from config import config
from parsl.data_provider.files import File
from parsl.utils import get_all_checkpoints
from parsl.dataflow.memoization import id_for_memo
import configparser

##function to read config file

def read_config(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    # Accessing the parameters
    dbscan_params = {
        'min_samples': config.getint('DBSCAN', 'min_samples', fallback=3),
        'eps': config.getfloat('DBSCAN', 'cluster_selection_epsilon', fallback=1),
    }
    blastn_params = {
        'max_search_queries_per_app' : config.getint('parsl', 'max_search_queries_per_app', fallback=None),
        'word_size': config.getint('blastn', 'word_size', fallback=None),
        'gapopen': config.getint('blastn', 'gapopen', fallback=None),
        'gapextend': config.getint('blastn', 'gapextend', fallback=None),
        'reward': config.getint('blastn', 'reward', fallback=None),
        'penalty': config.getint('blastn', 'penalty', fallback=None),
    }
    orfipy_params = {
        'min': config.getint('orfipy', 'min', fallback=1000),
        'max': config.getint('orfipy', 'max', fallback=None),
        'start': config.get('orfipy', 'start').split(',') if config.has_option('orfipy', 'start') else None,
        'stop': config.get('orfipy', 'stop').split(',') if config.has_option('orfipy', 'stop') else None,
    }
    mafft_params = {
        'op': config.getfloat('mafft', 'op', fallback=None),
        'ep': config.getfloat('mafft', 'ep', fallback=None),
        'maxiterate': config.getint('mafft', 'maxiterate', fallback=None),
    }
    raxml_params = {
        'tree': config.get('raxml', 'tree', fallback=None),
        'model': config.get('raxml', 'model', fallback=None),
        'opt_model': config.getboolean('raxml', 'opt-model', fallback=None),
        'opt_branches': config.getboolean('raxml', 'opt-branches', fallback=None),
        'blmin': config.getfloat('raxml', 'blmin', fallback=None),
        'blmax': config.getfloat('raxml', 'blmax', fallback=None),
    }
    astral_params = {
        'astral-pro' : config.getboolean('astral', 'astral-pro', fallback=True),
        'round': config.getint('astral', 'round', fallback=None),
        'subsample': config.getint('astral', 'subsample', fallback=None),
    }
    return dbscan_params, blastn_params, orfipy_params, mafft_params, raxml_params, astral_params

# Packages used in apps. Import to confirm correct installation
@python_app
def check_imports():
    import csv
    import json
    from shutil import which
    import shutil
    import numpy
    from sklearn.cluster import DBSCAN
    from scipy.sparse import lil_array
    from sklearn.metrics import silhouette_score
    from sklearn.neighbors import sort_graph_by_row_values
    from collections import defaultdict
    import tempfile
    from parsl.data_provider.files import File
    from parsl import bash_app
    import glob
    return True

# Required for making File compatible with checkpointing
@id_for_memo.register
def _(f: parsl.File, output_ref):
    return str(f)

# Throw error if file_path does not exist
def check_file(file_path):
    if not os.path.isfile(file_path):
        raise argparse.ArgumentTypeError(f"File {file_path} does not exist")
    
def check_catalog_files(CATALOG_PATH: str, filename: str):
    import os
    import json
    os.chdir(CATALOG_PATH)
    with open(filename) as f:
        data = json.load(f)
    assemblies = data["assemblies"]
    for assembly in assemblies:
        files = assembly["files"]
        for file in files:
            check_file(file["filePath"])

@python_app
def check_executables(inputs=(), outputs=()):
    from shutil import which
    outputs = [None] * len(inputs[0])
    for index in range(len(inputs[0])):
        outputs[index] = True if which(inputs[0][index]) != None else False
    return outputs

@python_app(cache=True)
def combine_files(inputs=(), outputs=()):
    with open(outputs[0], 'w') as fout:
        for finname in inputs:
            with open(finname) as fin:
                fout.write(fin.read())
    return outputs[0]

# Get annotation sequences and iterate over file pairs in annotations.txt
@bash_app(cache=True)
def annotations(line: str, CATALOG_PATH: str, SHARED_PATH: str, WORKING_DIR: str, outputs=()):
    import os
    os.chdir(WORKING_DIR)
    name, gff_file, fasta_file = line.split()
    return f'''{SHARED_PATH}/bedtools.static getfasta -fi {fasta_file} -bed {gff_file} -name > {fasta_file}.genes && echo {fasta_file}.genes > {outputs[0]}'''

@join_app
def start_annotations_func(CATALOG_PATH: str, SHARED_PATH: str, WORKING_DIR: str, inputs=(), outputs=()):
    with open(inputs[0], 'r') as fin:
        lines = fin.readlines()
    annotation_files = []
    annotations_future = []
    for line in lines:
        name, gff_file, fasta_file = line.split()
        annotation_file = name + ".annotation"
        annotations_future.append(annotations(line,  CATALOG_PATH, SHARED_PATH, WORKING_DIR, outputs=[annotation_file]))
        output_files.append(annotations_future.outputs[0])
    return combine_files(inputs=annotation_files, outputs=[outputs[0]])

# Relabel genes and iterate over files in genes.txt, taking first element of each line as a species name and the second the file of the genes
@bash_app(cache=True)
def relabel_genes(CATALOG_PATH: str, SHARED_PATH: str, WORKING_DIR: str, inputs=(), outputs=()):
    import os
    os.chdir(WORKING_DIR)
    name = inputs[0]
    input_file = inputs[1]
    return f'''cat {CATALOG_PATH}/{input_file} | {SHARED_PATH}/seqkit replace --f-by-name -p '.*' -r "{name}_gene{{nr}}" > {outputs[0]}'''

@join_app
def start_relabel_genes(CATALOG_PATH: str, SHARED_PATH: str, WORKING_DIR: str, inputs=()):
    with open(inputs[0], 'r') as fin:
        lines = fin.readlines()
    output_files = []
    for line in lines:
        name, input_file = line.split()
        output_file = File(f"{WORKING_DIR}/{name}.fasta")
        output_files.append((relabel_genes(CATALOG_PATH, SHARED_PATH, WORKING_DIR, inputs=[name, input_file], outputs=[output_file]).outputs[0]))
    return output_files

@python_app(cache=True)
def parse_catalog_func(WORKING_DIR, inputs=(), outputs=()):
    import os
    import json
    os.chdir(WORKING_DIR)
    filename = inputs[0]
    with open(filename) as f:
        data = json.load(f)
    assemblies = data["assemblies"]
    with open(outputs[0],"w") as genes_fout:
        with open(outputs[1],"w") as genomes_fout:
            with open(outputs[2],"w") as annotations_fout:
                for assembly in assemblies:
                    if "accession" in assembly:
                        files = assembly["files"]
                        cds_found = False
                        for fi in files:
                            if "fileType" in fi and fi["fileType"] == "CDS_NUCLEOTIDE_FASTA":
                                genes_fout.write(assembly["accession"] + " " + fi["filePath"] + "\n")
                                cds_found = True
                        if not cds_found:
                            for fi in files:
                                if "fileType" in fi and fi["fileType"] == "GENOMIC_NUCLEOTIDE_FASTA":
                                    gff_found = False
                                    for file2 in files:
                                        if "fileType" in file2 and fi["fileType"] == "GFF3":
                                            annotations_fout.write(assembly["accession"] + " " + file2["filePath"] + " " + fi["filePath"] + "\n")
                                            gff_found = True
                                    if not gff_found:
                                        genomes_fout.write(assembly["accession"] + " " + fi["filePath"] + "\n")
    return True

@bash_app(cache=True)
def find_orfs(name: str, CATALOG_PATH: str, SHARED_PATH: str, WORKING_DIR: str, inputs=(), outputs=(), params = None):
    import os
    os.chdir(WORKING_DIR)
    subject = inputs[0]
    output = outputs[0]
    orf_output = f"{output}.tmporf"
    PWD = os.getcwd()
    command = f'''orfipy --dna {orf_output} --ignore-case --outdir {PWD}'''
    if params:
        if params['start'] != None:
            command += f" --start {','.join(params['start'])}"
        if params['stop'] != None:
            command += f" --stop {','.join(params['stop'])}"
        if params['min'] != None:
            command += f" --min {params['min']}"
        if params['max'] != None:
            command += f" --max {params['max']}"
    else:
        command += " --min 1000"
    command += f''' {subject}'''
    command += f''' && cat {orf_output} | {SHARED_PATH}/seqkit replace --f-by-name -p '.*' -r "{name}_gene{{nr}}" > {output} && rm {orf_output} && echo {output}'''
    return command

@join_app
def start_find_orfs(CATALOG_PATH: str, SHARED_PATH: str, WORKING_DIR: str, inputs=(), outputs=(), params=None):
    from parsl import bash_app
    from parsl.data_provider.files import File
    tasks = []
    output_files = []
    with open(inputs[0], 'r') as fin:
        lines = fin.readlines()
    for line in lines:
        name, input_file = line.split()
        output_file = File(f"{WORKING_DIR}/blast_{name}.fasta")
        app = find_orfs(name, CATALOG_PATH, SHARED_PATH, WORKING_DIR, inputs=[File(f"{CATALOG_PATH}/{input_file}")], outputs=[output_file], params=params)
        output_files.append(app.outputs[0])
    return output_files

@bash_app(cache=True)
def build_blast_db(WORKING_DIR: str, inputs=(), outputs=()): # in: cat *.fasta > all_species.all_fasta, out: genes.db
    return f'''cd {WORKING_DIR} && rm -f genes.db* && cat {WORKING_DIR}/*.fasta > all_species.all_fasta && makeblastdb -input_type fasta -in all_species.all_fasta -blastdb_version 5 -title "grouping genes" -dbtype nucl -out {outputs[0]} && touch {outputs[0]}'''

@bash_app(cache=True)
def search_blast(WORKING_DIR: str, blast_evalue: str, inputs=(), outputs=(), params = None):
    import os
    os.chdir(WORKING_DIR)
    query = inputs[0]
    database = inputs[1]
    outfile = outputs[0]
    base_command =  f'''blastn -query {query} -db {database} -out {outfile} -task dc-megablast -evalue {blast_evalue} -outfmt "6 qaccver saccver evalue" -num_threads 2'''
    if params:
        if params['word_size']:
            base_command += f" -word_size {params['word_size']}"
        if params['gapopen']:
            base_command += f" -gapopen {params['gapopen']}"
        if params['gapextend']:
            base_command += f" -gapextend {params['gapextend']}"
        if params['reward']:
            base_command += f" -reward {params['reward']}"
        if params['penalty']:
            base_command += f" -penalty {params['penalty']}"    
    return base_command + f" && rm {query}"

@bash_app(cache=True)
def split_fasta(WORKING_DIR: str, SHARED_PATH: str, max_queries: int, inputs=()):
    return f"{SHARED_PATH}/seqkit split --force --by-size {max_queries} {inputs[0]}"

@bash_app(cache=True)
def copy_files_with_pattern_to_file(DIR: str, inputs=(), outputs=()):
    return f"cd {DIR} && echo 'copying to {outputs[0]}' && rm -f {outputs[0]} && for i in {inputs[0]}; do cat $i >> {outputs[0]} && rm $i; done && echo 'copied to {outputs[0]}'"

@join_app
def start_search_blast(WORKING_DIR: str, blast_evalue: str, params=None, inputs=(), outputs=()):
    database = inputs[0]
    queries = inputs[1]
    queries.extend(inputs[2])
    output_files = []
    for query in queries:
        fileout = File(f"{query.filepath}.tab")
        output_files.append(search_blast(WORKING_DIR, blast_evalue, inputs=[query, database], outputs=[fileout], params=params).outputs[0])
    with open(outputs[0], 'w') as fout:
        for filename in output_files:
            print(filename.filepath, file=fout)
    return output_files

@join_app
def start_search_blast_with_split(WORKING_DIR: str, SHARED_PATH: str, blast_evalue: str, params=None, inputs=(), outputs=()):
    import glob
    database = inputs[0]
    queries = inputs[1]
    queries.extend(inputs[2])
    output_dirs = []
    output_files = []
    file_splits = []
    all_search_results = []
    max_search_queries = params['max_search_queries_per_app']
    for query in queries:
        file_splits.append(split_fasta(WORKING_DIR, SHARED_PATH, max_search_queries, inputs=[query]))
    for split in file_splits:
        split.result() # wait for files to be split before proceeding
    for query in queries:
        dir = f"{query}.split"
        for file in glob.glob(f"{query}.split/*.fasta"):
            filein = File(f"{file}")
            fileout = File(f"{file}.tab")
            output_files.append(search_blast(WORKING_DIR, blast_evalue, inputs=[filein, database], outputs=[fileout], params=params).outputs[0])
        output_dirs.append(f"{dir}")
    for output_file in output_files:
        output_file.result() # wait for searches before proceeding
    for output_dir, query in zip(output_dirs, queries):
        search_results = File(f"{query}.tab")
        all_search_results.append(copy_files_with_pattern_to_file(output_dir, inputs=["*.fasta.tab"], outputs=[search_results]).outputs[0])
    with open(outputs[0], 'w') as fout:
        for filename in all_search_results:
            print(filename.filepath, file=fout)
    return all_search_results

@bash_app(cache=True)
def copy_blast_to_csv(WORKING_DIR: str, inputs=(), outputs=()):
    with open(inputs[0], 'r') as fin:
        lines = fin.readlines()
    file_combine_cmd = ""
    for input in lines:
        query = input.strip()
        file_combine_cmd += f"echo 'copying {query} in copy_blast_to_csv' && cat {query} >> {outputs[0].filepath} && rm {query} && "
    return f'''cd {WORKING_DIR} && rm -f {outputs[0].filepath} && {file_combine_cmd} echo "{outputs[0].filepath}"'''

@python_app(cache=True)
def group(WORKING_DIR, max_group_size, inputs=(), outputs=(), params=None):
    import os
    os.chdir(WORKING_DIR)
    import csv
    import numpy as np
    from sklearn.cluster import DBSCAN
    from scipy.sparse import lil_array
    from sklearn.metrics import silhouette_score
    from sklearn.neighbors import sort_graph_by_row_values
    from collections import defaultdict
    from parsl.data_provider.files import File

    # Define the path to your BLAST results file
    blast_results_file = inputs[0]  # Replace with your file path
    
    # Get parameters
    eps = 1
    min_samples = 3
    if params:
        eps = params['eps'] if params['eps'] != None else eps
        min_samples = params['min_samples'] if params['min_samples'] != None else min_samples

    # Define the minimum number of clusters as 1/N (N specified via command line)
    # Replace N with the appropriate value or use a command-line argument parser
    N = 100

    # Initialize dictionaries to map sequence IDs to matrix indices
    sequence_to_index = {}
    index_to_sequence = {}

    # Create a dictionary of dictionaries to store the similarity scores as a sparse matrix
    similarity_scores = {}

    # Read the BLAST results file and populate the dictionaries and similarity_scores
    with open(blast_results_file, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')  # Adjust delimiter if needed
        for row in reader:
            query_sequence = row[0]  # Replace with the column index of the query sequence
            subject_sequence = row[1]  # Replace with the column index of the subject sequence
            similarity_score = float(row[2])  # Replace with the column index of the similarity score

            # Split query_sequence and subject_sequence on ORF or gene
            # Only store distance if the sequences are on two different species
            if query_sequence.partition("_ORF")[0].partition("_gene")[0] != subject_sequence.partition("_ORF")[0].partition("_gene")[0]:

                # Check if the query sequence is in the dictionary; if not, assign an index
                if query_sequence not in sequence_to_index:
                    index = len(sequence_to_index)
                    sequence_to_index[query_sequence] = index
                    index_to_sequence[index] = query_sequence

                # Check if the subject sequence is in the dictionary; if not, assign an index
                if subject_sequence not in sequence_to_index:
                    index = len(sequence_to_index)
                    sequence_to_index[subject_sequence] = index
                    index_to_sequence[index] = subject_sequence

                # Store the similarity score in the sparse matrix
                query_index = sequence_to_index[query_sequence]
                subject_index = sequence_to_index[subject_sequence]
                similarity_scores[(query_index, subject_index)] = similarity_score
                similarity_scores[(subject_index, query_index)] = similarity_score  # Symmetric matrix

    # Determine the number of sequences
    num_sequences = len(sequence_to_index)
    print("Sequences: " + str(num_sequences))

    # Create a sparse distance matrix
    distance_matrix = lil_array((num_sequences, num_sequences), dtype=float)

    # Fill the sparse distance matrix with the similarity scores
    for (i, j), score in similarity_scores.items():
        distance_matrix[i, j] = score

    distance_matrix = distance_matrix.tocsr()
    sort_graph_by_row_values(distance_matrix)

    print("Nonzeros in distance matrix: " + str(distance_matrix.count_nonzero()))

    # Compute DBSCAN
    # whether eps is 0.1 or 1, the groups are the same (above the threshold of the blast search)
    db = DBSCAN(metric="precomputed", eps = eps, min_samples = min_samples, n_jobs=-1).fit(distance_matrix)
    labels = db.labels_
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise_ = list(labels).count(-1)

    print("Estimated number of clusters: %d" % n_clusters_)
    print("Estimated number of noise points: %d" % n_noise_)

    # Print out the groups with suffix .seq_list.fasta
    # for each label in labels, get all db[labels == label] and print its members
    groups = defaultdict(list)
    for i in range(num_sequences):
        if labels[i] != 1:
            groups[labels[i]].append(index_to_sequence[i])

    output_files = []
    for label, group in groups.items():
        if len(group) > 3 and len(group) < max_group_size:
            f = File(f"{WORKING_DIR}/group{label}.seq_list")
            output_files.append(f)
            with open(f, "w") as fout:
                for g in group:
                    print(g, file=fout)
    with open(outputs[0], 'w') as fout:
        for filename in output_files:
            print(filename, file=fout)


@bash_app(cache=True)
def seq_list_to_alignment(WORKING_DIR: str, SHARED_PATH: str, remove_files: bool, inputs=(), outputs=(), params=None):
    input_file = inputs[0]
    output_file = outputs[0]
    rm_fasta = ""
    if remove_files:
        rm_fasta = f'&& rm {input_file}.fasta'
    mafft_params_str = ""
    if params:
        if params['op']:
            mafft_params_str += f" --op {params['op']}"
        if params['ep']:
            mafft_params_str += f" --ep {params['ep']}"
        if params['maxiterate']:
            mafft_params_str += f" --maxiterate {params['maxiterate']}"
    return f'''search_list=$(grep -f {input_file} -l {WORKING_DIR}/all_species.all_fasta) && {SHARED_PATH}/seqkit grep -f {input_file} -o {input_file}.fasta ${{search_list}} && mafft --auto --thread -1 {mafft_params_str} {input_file}.fasta > {input_file}.aln {rm_fasta} && sed -i 's/_gene:.*$//g' {input_file}.aln && sed -i 's/_CDS:.*$//g' {input_file}.aln && sed -i 's/_ORF:.*$//g' {input_file}.aln && {SHARED_PATH}/seqkit rmdup -n {input_file}.aln > {input_file}.tmp && mv {input_file}.tmp {output_file} && echo "alignment output at {output_file}"'''


@bash_app(cache=True)
def alignment_to_gene_tree(remove_files: bool, inputs=(), outputs=(), params = None):
    input_file = inputs[0]
    output_prefix = inputs[0]
    rm_aln = ""
    if remove_files:
        rm_aln = f'&& rm {input_file}'
    default_raxml_params = {
        'tree': 'rand{1}',  # Default tree specification
        'model': 'GTR+G',  # Default model
        'opt_model': True,  # Default optimization of model
        'opt_branches': True,  # Default optimization of branches
        'blmin': 1e-6,  # Default minimum branch length
        'blmax': 100,  # Default maximum branch length
    }
    raxml_command = f'''raxml-ng --msa {input_file} --prefix {output_prefix}'''
    if params:
        if params['tree']:
            raxml_command += f" --tree {params['tree']}"
        else:
            raxml_command += f" --search1"
        if params['model']:
            raxml_command += f" --model {params['model']}"
        else:
            raxml_command += f" --model {default_raxml_params['model']}"
        if params['opt_model']:
            raxml_command += " --opt_model"
        if params['opt_branches']:
            raxml_command += " --opt_branches"
        if params['blmin']:
            raxml_command += f" --blmin {params['blmin']}"
        if params['blmax']:
            raxml_command += f" --blmax {params['blmax']}"
    else:
        raxml_command += f" --search1 --model {default_raxml_params['model']}"
    return f'''echo "running raxml-ng with input of {input_file}" && rm -f {input_file}.raxml.* && {raxml_command}'''

@bash_app(cache=True)
def select_random_genes(max_trees, inputs=(), outputs=()):
    return f'''shuf -n {max_trees} {inputs[0]} > {outputs[0]}'''

@join_app
def start_gene_trees(WORKING_DIR: str, SHARED_PATH: str, max_trees: int, remove_files: bool, inputs=(), outputs=(), mparams = None, rparams = None):
    with open(inputs[0], 'r') as fin:
        genes_for_trees = fin.readlines()
    tree_files = []
    for gene_file in genes_for_trees:
        gene_file = gene_file.strip()
        alignment_file = File(f"{gene_file}.aln")
        tree_file = File(f"{gene_file}.aln.raxml.bestTree")
        align_task = seq_list_to_alignment(WORKING_DIR, SHARED_PATH, remove_files, inputs=[gene_file], outputs=[alignment_file], params = mparams)
        tree_task = alignment_to_gene_tree(remove_files, inputs=[align_task.outputs[0]], outputs=[tree_file], params = rparams)
        # TODO: remove intermediate files if remove_files
        tree_files.append(tree_task.outputs[0])
    with open(outputs[0], 'w') as fout:
        for filename in tree_files:
            print(filename.filepath, file=fout)
    return tree_files

@bash_app(cache=True)
def astral(inputs=(), outputs=(), params = None):
    with open(inputs[0], 'r') as fin:
        lines = fin.readlines()
    bestTrees = ' '.join(f.strip() for f in lines)
    astral_command = ""
    if params:
        if params['astral-pro']:
            astral_command = f"astral-pro -i all_trees.out -o {outputs[0]}"
            if params['round']:
                astral_command += f" --round {params['round']}"
            if params['subsample']:
                astral_command += f" --subsample {params['subsample']}"
        else:
            astral_command = f"astral4 -o {outputs[0]}"
            if params['round']:
                astral_command += f" -r {params['round']}"
            if params['subsample']:
                astral_command += f" -s {params['subsample']}"
            astral_command += " all_trees.out"
    return f'''cat {bestTrees} > all_trees.out && sed -i 's/_gene[^:]*//g' all_trees.out && sed -i 's/_ORF[^:]*//g' all_trees.out && sed -i 's/_DN[^:]*//g' all_trees.out && {astral_command}'''

@python_app(cache=True)
def make_temp_dir(input_file: str, output_file: str):
    import tempfile
    import os
    return tempfile.mkdtemp(prefix=os.getcwd()+'/poplar_tmp_')

if __name__ == "__main__":
    config.retries = 2
    config.checkpoint_mode = 'task_exit'
    config.checkpoint_files = get_all_checkpoints()

    with parsl.load(config):

        parser = argparse.ArgumentParser()
        parser.add_argument('input_file', help='path to input json file', type=str)
        parser.add_argument('-o', '--output_file', help='path to output file (default:  %(default)s)', default="output.tree", type=str, required=False)
        parser.add_argument('-t', '--max_trees', help='maximum gene trees (default:  %(default)s)', default=50, type=int, required=False)
        parser.add_argument('-g', '--max_group_size', help='maximum number of sequences permitted in a gene group (default:  %(default)s)', default=100, type=int, required=False)
        parser.add_argument('-e', '--blast_evalue', help='evalue used for blastn search in finding related gene sequences (default:  %(default)s)', default='1e-20', type=str, required=False)
        parser.add_argument('-f', '--temp_files', help='keep intermediate files, including gene trees  (default:  %(default)s)', type=bool, default=False, required=False)
        parser.add_argument('-c', '--config_file', help='path to configuration file (optional)', type=str, required=False)  # New argument for config file
        args = parser.parse_args()

        # Read configuration file if provided
        dbscan_params = None
        blastn_params = None
        orfipy_params = None
        mafft_params = None
        raxml_params = None
        astral_params = None
        if args.config_file:
            dbscan_params, blastn_params, orfipy_params, mafft_params, raxml_params, astral_params = read_config(args.config_file)  # Assuming read_config returns a dictionary of parameters

        catalog_file_name = os.path.abspath(args.input_file)
        output_file_name = os.getcwd() + "/" + args.output_file
        if not float(args.blast_evalue) < 1:
            print(f"Error: blast_evalue must be a number less than 1")
            exit()
        check_file(args.input_file)

        print(f"Input file: {catalog_file_name}")
        print(f"Output file: {output_file_name}")

        CATALOG_PATH = os.path.dirname(catalog_file_name)
        SHARED_PATH = os.path.dirname(os.path.abspath(__file__))
        
        executables = ["echo", "cat", "rm", "touch", "grep", "mv", "sed", "shuf", f"{SHARED_PATH}/bedtools.static", f"{SHARED_PATH}/seqkit", "makeblastdb", "blastn", "orfipy", "mafft", "raxml-ng", "astral-pro"]
        valid_executables = check_executables(inputs=[executables]).result()

        for exe, valid in zip(executables, valid_executables):
            if not valid:
                print(f"Error: Required command {exe} not found.")
                exit()

        if not check_imports().result():
            print(f"Error: Failed to import all required packages.")
            exit()

        WORKING_DIR = make_temp_dir(catalog_file_name, output_file_name).result()
        os.chdir(WORKING_DIR)
        print(f"Using temporary directory: {WORKING_DIR}")
        check_catalog_files(CATALOG_PATH, catalog_file_name)

        catalog_file_name = File(catalog_file_name)
        gene_file = File(WORKING_DIR + "/genes.txt")
        genomes_file = File(WORKING_DIR + "/genomes.txt")
        annotations_file = File(WORKING_DIR + "/annotations.txt")
        annotation_genes_file = File(WORKING_DIR + "/annotation_genes.txt")
        relabeled_gene_file= File(WORKING_DIR + "/relabeled_genes.txt")
        query_genes_file = File(WORKING_DIR + "/query_genes.query_fasta")
        all_genes_file = File(WORKING_DIR + "/all_species.all_fasta")
        blast_db_file = File(WORKING_DIR + "/genes.db")
        blast_search_results = File(WORKING_DIR + "/blast_search_results.txt")
        blast_csv = File(WORKING_DIR + "/blast_results.csv")
        group_list_file = File(WORKING_DIR + "/grouplist.txt")
        selected_group_list_file = File(WORKING_DIR + "/selectedgrouplist.txt")
        gene_tree_list_file = File(WORKING_DIR + "/genetreelist.txt")
        output_tree_file = File(output_file_name)

        print("Adding catalog parsing app to workflow")
        parse_catalog_future = parse_catalog_func(WORKING_DIR, inputs=[catalog_file_name], outputs=[gene_file, genomes_file, annotations_file])
        print("Adding app to workflow to finding sequences from annotations")
        start_annotations = start_annotations_func(CATALOG_PATH, SHARED_PATH, WORKING_DIR, inputs=[parse_catalog_future.outputs[2]], outputs=[annotation_genes_file])
        combine_genes_and_annotations = combine_files(inputs=[parse_catalog_future.outputs[0], start_annotations.outputs[0]], outputs=[relabeled_gene_file])
        print("Adding app to workflow to relabel genes")
        relabel_genes_future = start_relabel_genes(CATALOG_PATH, SHARED_PATH, WORKING_DIR,inputs=[combine_genes_and_annotations.outputs[0]])
        print("Adding app to workflow to find ORFs in unannotated genomes")
        find_orfs_future = start_find_orfs(CATALOG_PATH, SHARED_PATH, WORKING_DIR, inputs=[parse_catalog_future.outputs[1]], outputs=[all_genes_file], params=orfipy_params)
        print("Adding app to workflow to build BLAST Database")
        build_blast_db_future = build_blast_db(WORKING_DIR, inputs=[find_orfs_future.outputs[0], relabel_genes_future.result()], outputs=[blast_db_file])
        print("Adding app to workflow to search BLAST DB for matching sequences")
        blast_search_future = None
        if blastn_params == None or blastn_params['max_search_queries_per_app'] == None:
            blast_search_future = start_search_blast(WORKING_DIR, args.blast_evalue, params=blastn_params, inputs=[build_blast_db_future.outputs[0], relabel_genes_future.result(), find_orfs_future.result()], outputs=[blast_search_results])
        else:
            blast_search_future = start_search_blast_with_split(WORKING_DIR, SHARED_PATH, args.blast_evalue, params=blastn_params, inputs=[build_blast_db_future.outputs[0], relabel_genes_future.result(), find_orfs_future.result()], outputs=[blast_search_results])
        copy_future = copy_blast_to_csv(WORKING_DIR, inputs=[blast_search_future.outputs[0]], outputs=[blast_csv])
        print("Adding app to workflow to group the sequences")
        grouping_future = group(WORKING_DIR, args.max_group_size, inputs=[copy_future.outputs[0]], outputs=[group_list_file])
        print("Adding app to workflow to generate gene trees")
        gene_list_future = select_random_genes(args.max_trees, inputs=[grouping_future.outputs[0]], outputs=[selected_group_list_file])
        gene_tree_future = start_gene_trees(WORKING_DIR, SHARED_PATH, args.max_trees, not args.temp_files, inputs=[gene_list_future.outputs[0]], outputs=[gene_tree_list_file]) 
        print("Adding app to workflow to generate species tree", flush=True)
        species_tree_future = astral(inputs=[gene_tree_future.outputs[0]], outputs=[output_tree_file], params = astral_params)
        # AppFuture result() is a blocking call until the app has completed
        # Wait for parsing catalog
        parse_catalog_future.result()
        print("Parsed catalog", flush=True)
        # Wait for annotations
        start_annotations.result()
        combine_genes_and_annotations.result()
        print("Found sequences from annotations", flush=True)
        # Wait for relabeling genes
        relabel_genes_future.result()
        print("Relabeled genes", flush=True)
        # Wait for finding ORFs
        find_orfs_future.result()
        print("Found ORFs", flush=True)
        # Wait for building BLAST DB
        blast_search_future.result()
        print("Built BLAST DB", flush=True)
        # Wait for searching BLAST
        blast_search_future.result()
        copy_future.result()
        print("Searched BLAST DB", flush=True)
        # Wait for grouping
        grouping_future.result()
        print("Grouped sequences", flush=True)
        # Wait for gene alignments
        gene_list_future.result()
        print("Aligned gene sequences", flush=True)
        # Wait for gene trees
        gene_tree_future.result()
        print("Constructed gene trees", flush=True)
        # Wait for species tree
        species_tree_future.result()
        if not args.temp_files:
            import shutil
            shutil.rmtree(WORKING_DIR)

        print("Constructed species tree:", flush=True)
        system(f"cat {output_tree_file}")
