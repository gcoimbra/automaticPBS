#!/bin/env python3
from enum import Enum
from re import split
from typing import Optional

import pandas

import subprocess

import pytest
import tests


class FirstSort(Enum):
    memory = 0
    cpu = 1


class Requirements:

    def __init__(self, sort: FirstSort, mem_min: Optional[int] = None, mem_max: Optional[int] = None,
                 cpu_max: Optional[int] = None, cpu_min: Optional[int] = None,
                 mem_min_per_core: Optional[int] = None,
                 ):
        self.mem_min = mem_min
        self.mem_max = mem_max

        self.cpu_max = cpu_max
        self.cpu_min = cpu_min

        self.mem_min_per_core = mem_min_per_core

        self.sort = sort


def cpuMem(hinfo: str, requirements: Requirements, ):
    if requirements.mem_min and requirements.mem_min_per_core:
        assert (requirements.mem_min_per_core is None) or (requirements.mem_min == 1)
    if requirements.cpu_max and requirements.cpu_min:
        assert requirements.cpu_min <= requirements.cpu_max
    if requirements.mem_max and requirements.mem_min:
        assert requirements.mem_min < requirements.mem_max

    if requirements.mem_max and requirements.mem_min_per_core and requirements.cpu_min:
        assert requirements.cpu_min * requirements.mem_min_per_core <= requirements.mem_max

    b = hinfo.split('\n')
    del b[0]  # column description
    del b[0]  # column description
    del b[-1]  # total nodes

    # TODO: requirements GB per core requirements

    table = []
    for line in b:
        table.append(split('\s+', line))

    del table[-1][-1]  # remove extra space
    table = pandas.DataFrame(table, columns=['node', 'cpuAvail', 'cpuAlloc', 'cpuFree',
                                             'memAvail', 'memAlloc', 'memFree', 'State'])
    table = table.loc[~(table.State.str.contains('down') | table.State.str.contains('state-unknown'))]
    table = table[table.State.str.contains('free') | table.State.str.contains('job-busy')]

    assert len(table) > 1
    memCols = ['memAvail', 'memAlloc', 'memFree']
    cpuCols = ['cpuAvail', 'cpuAlloc', 'cpuFree']

    for col in memCols:
        table[col] = table[col].str.replace('GB', '')

    table[memCols] = table[memCols].astype('float')
    table[cpuCols] = table[cpuCols].astype('int')

    if requirements.mem_min:
        tableCheck = table[table.memFree >= requirements.mem_min]
        if len(tableCheck) == 0:
            raise RuntimeError(f"no nodes with required memory available. memory required {requirements.mem_min}"
                               f"node with max memory available: {table['memFree'].max()}")
        else:
            table = tableCheck

    if requirements.cpu_min:
        tableCheck = table[table.cpuFree >= requirements.cpu_min]
        if len(tableCheck) == 0:
            raise RuntimeError(f"no nodes with required cpu available. cpu required {requirements.cpu_min}"
                               f"node with max cpu available: {table['cpuFree'].max()}")
        else:
            table = tableCheck

    if requirements.sort == FirstSort.cpu:
        sortCols = ['cpuFree', 'memFree']
    else:

        sortCols = ['memFree', 'cpuFree']
    table = table.sort_values(by=sortCols, ascending=False)

    # Base case, just make sure any mem and cpu are seelcted
    selectedCpu = table.iloc[0].cpuFree
    selectedMem = table.iloc[0].memFree

    for _, selectedNode in table.iterrows():

        selectedCpu = selectedNode.cpuFree
        selectedMem = selectedNode.memFree

        # The order of these checks matter, we must make sure that
        if requirements.cpu_max and selectedNode.cpuFree >= requirements.cpu_max:
            print('cpu max requirement fulfilled ')
            selectedCpu = requirements.cpu_max

        if requirements.mem_min_per_core:
            if selectedMem >= requirements.mem_min_per_core * selectedCpu:
                if requirements.mem_max and selectedNode.memFree >= requirements.mem_max:
                    print('mem max requirement fulfilled ')
                    selectedMem = requirements.mem_max
                break  # mem_min_per_core has priority over mem_max
        else:
            if requirements.mem_max and selectedNode.memFree >= requirements.mem_max:
                print('mem max requirement fulfilled ')
                selectedMem = requirements.mem_max
                break

    return int(round(selectedMem)), int(round(selectedCpu))


# TODO: requirements, GB per core
if __name__ == "__main__":
    # TODO: write tests
    # TODO: fuzzy brek tests?
    import sys
    import subprocess
    import argparse

    parser = argparse.ArgumentParser(
        prog='AutoPBSRequirements',
        description='Get max mem or cpu available in cluster', )

    parser.add_argument('--cpu_min', required=False)
    parser.add_argument('--mem_min', required=False)
    parser.add_argument('--cpu_max', required=False)

    parser.add_argument('--mem_max', required=False)

    parser.add_argument('--mem_min_per_core', required=False)

    parser.add_argument('--sort', choices=['cpu', 'mem'], required=True)
    parser.add_argument('--pbs_config_file', required=True)
    parser.add_argument('--out_file', required=True)

    args = parser.parse_args()

    requirementsDict = {
        'cpu_max': float(args.cpu_max) if args.cpu_max else None,
        'cpu_min': float(args.cpu_min) if args.cpu_min else 1,
        'mem_min': float(args.mem_min) if args.mem_min else 1,
        'mem_max': float(args.mem_max) if args.mem_max else None,
        'mem_min_per_core': float(args.mem_min_per_core) if args.mem_min_per_core else None,
    }

    if args.sort == 'cpu':
        firstSort = FirstSort.cpu
    else:
        firstSort = FirstSort.memory
    requirements = Requirements(sort=firstSort, **requirementsDict)

    hinfo = subprocess.run(['hinfo'], capture_output=True).stdout.decode('ascii')
    #hinfo = tests.tests[1]
    mem, cpu = cpuMem(hinfo, requirements)

    print('found mem', mem, 'and cpu', cpu, 'before margin')

    file = open(args.pbs_config_file, 'r').read()

    outfile = open(args.out_file, 'w+')
    file = file.replace('${PPN}', str(cpu)).replace('${MEM}', str(mem))
    if mem < 22: # less than 22 GB is not high_mem
    	file = file.replace('#PBS -q high_mem','')
    outfile.write(file)
    outfile.close()

    outFile2 = open('clusterconf', 'w+')
    outFile2.write(f'{mem},{cpu}')
    outFile2.close()


def test_all():
    for hinfo in tests.values():
        requirements = Requirements(FirstSort.cpu)

        members = [attr for attr in dir(requirements) if
                   not callable(getattr(requirements, attr)) and not attr.startswith("__")]
        members.remove('sort')
        for member in members:
            oldattr = getattr(requirements, member)
            setattr(requirements, member, 999)
            print(oldattr, member, getattr(requirements, member))
            with pytest.raises(RuntimeError) as info:
                mem, cpu = cpuMem(hinfo, requirements)
            setattr(requirements, member, oldattr)


def test_max_bigger_than_min():
    for hinfo in tests.values():
        requirements = Requirements(FirstSort.cpu, cpu_max=9, cpu_min=16)
        with pytest.raises(AssertionError) as einfo:
            mem, cpu = cpuMem(hinfo, requirements)
        requirements = Requirements(FirstSort.cpu, cpu_max=9, cpu_min=16)
        with pytest.raises(AssertionError) as einfo:
            mem, cpu = cpuMem(hinfo, requirements)
