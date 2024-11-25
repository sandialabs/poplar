import parsl
from parsl.config import Config
from parsl.providers import SlurmProvider
from parsl.executors import HighThroughputExecutor
from parsl.providers import LocalProvider
from parsl.monitoring.monitoring import MonitoringHub
from parsl.addresses import address_by_hostname

"""
This config is written for Sandia's Kahuna. Each block will be 2 nodes allocated for 2 hours 10 minutes.
"""
config = Config(
     executors=[
          HighThroughputExecutor(
               label="kahuna",
               worker_debug=False,
               cores_per_worker=2.0,  # each worker uses only 2 cores of a node
               provider=LocalProvider(
                    init_blocks=1,
                    max_blocks=1,
                    worker_init='conda activate poplar_env; export PATH=$PATH:$BLAST:$RAXML:$ASTRAL',  # requires conda environment with parsl
               ),
          )
     ],
     monitoring=MonitoringHub( #  pip install 'parsl[monitoring]'
          hub_address=address_by_hostname(),
          hub_port=55055,
          monitoring_debug=False,
          resource_monitoring_interval=10,
     ),
     # Then use `parsl-visualize`, which require `conda install flask panda plotly networkx pydot; pip install flask_sqlalchemy`
     # Connect to the server by using `ssh -L 50000:127.0.0.1.:8080 username@cluster` and then going to 127.0.0.1:50000 on the local machine's browser

)
