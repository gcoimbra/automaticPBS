# automaticPBS
Simple script to automatically retrieve the best configuration in terms of cpu and memory that is currently available in a OpenPBS cluster according to requirements.

## Motivation
If you don't want your job to enter the cluster queue just because you set statically your memory and cpu requirements and don't want to look at hinfo everytime?
Dynamically get the currently best specs according to your requirements in the cluster based on hinfo output.

# warning. this is a very alpha stage script.

## Usage
» python3 automaticMemCPUPBS.py
usage: AutoPBSRequirements [-h] [--cpu_min CPU_MIN] [--mem_min MEM_MIN] [--cpu_max CPU_MAX]
                           [--mem_max MEM_MAX] [--mem_min_per_core MEM_MIN_PER_CORE] --sort
                           {cpu,mem} --pbs_config_file PBS_CONFIG_FILE --out_file OUT_FILE
AutoPBSRequirements: error: the following arguments are required: --sort, --pbs_config_file, --out_file

» python3 automaticMemCPUPBS.py --mem_min_per_core 2 --cpu_min 20 --sort cpu --pbs_config_file sample.pbs --out_file out.pbs
mem max requirement fulfilled 
found mem 128 and cpu 64 before margin

In this sample, I sort the nodes based 

## Observations

You can use this as a script or call directly cpuMem function with requirements dict filled.
If the script can't fullfil the minimum requirements you set, an exception is raised.

The values obtained for mem and cpu are written to a file "clusterconf" on the app directory to be used in spark like applications that need to know cpu and memory in advance.


Some applications will use more memory if you have more cores, like spark, so I advise use mem_min_per_core. The script tries to fullfil your requirements for minimum and maximum cpu,
after the number of cpu is found, the script will assert that you have at least a minimum amout of memory for that number of cores .
