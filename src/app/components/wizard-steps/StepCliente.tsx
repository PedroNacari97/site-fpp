import React from 'react';
import { Option, StepProps, TipoEmissao } from './types';

const TIPOS: Option[] = [
  { id: 'conta_cliente', label: 'Conta do Cliente', description: 'Cliente usa suas próprias milhas' },
  { id: 'conta_administradora', label: 'Conta Administradora', description: 'Empresa emite com conta administrada' },
  { id: 'emissor_parceiro', label: 'Emissor Parceiro', description: 'Emissão com parceiro externo' },
];

const PROGRAMAS: Option[] = [
  { id: 'latam', label: 'LATAM Pass', color: 'bg-red-500' },
  { id: 'smiles', label: 'Smiles', color: 'bg-orange-500' },
  { id: 'azul', label: 'TudoAzul', color: 'bg-blue-500' },
  { id: 'privilege', label: 'Privilege Club', color: 'bg-purple-500' },
];

const CLIENTES: Option[] = [
  { id: '1', label: 'João Silva - CPF 123.456.789-00' },
  { id: '2', label: 'Maria Souza - CPF 987.654.321-00' },
];

export const StepCliente: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  return (
    <div className='space-y-6'>
      <h2 className='text-2xl font-semibold text-white'>Dados do Cliente</h2>

      <div>
        <p className='text-sm text-gray-300 mb-2'>Tipo de Emissão *</p>
        <div className='grid md:grid-cols-3 gap-3'>
          {TIPOS.map((tipo) => (
            <button
              type='button'
              key={tipo.id}
              onClick={() => onUpdate({ tipoEmissao: tipo.id as TipoEmissao })}
              className={`p-4 rounded-xl border text-left transition ${data.tipoEmissao === tipo.id ? 'border-blue-500 bg-blue-500/20' : 'border-gray-700 bg-gray-900'}`}
            >
              <p className='text-white font-medium'>{tipo.label}</p>
              <p className='text-xs text-gray-400'>{tipo.description}</p>
            </button>
          ))}
        </div>
        {errors.tipoEmissao && <p className='text-red-400 text-sm mt-1'>{errors.tipoEmissao}</p>}
      </div>

      <div>
        <label className='text-sm text-gray-300'>Cliente *</label>
        <select
          className='mt-1 w-full rounded-lg bg-gray-900 border border-gray-700 p-3 text-white'
          value={data.clienteId}
          onChange={(e) => onUpdate({ clienteId: e.target.value })}
        >
          <option value=''>Selecione...</option>
          {CLIENTES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        {errors.clienteId && <p className='text-red-400 text-sm mt-1'>{errors.clienteId}</p>}
      </div>

      <div>
        <label className='text-sm text-gray-300'>Programa de Milhas *</label>
        <div className='grid md:grid-cols-4 gap-3 mt-2'>
          {PROGRAMAS.map((p) => (
            <button
              type='button'
              key={p.id}
              onClick={() => onUpdate({ programaId: p.id })}
              className={`p-4 rounded-xl border ${data.programaId === p.id ? 'border-blue-400 bg-blue-500/20' : 'border-gray-700 bg-gray-900'}`}
            >
              <span className={`inline-block w-3 h-3 rounded-full ${p.color}`} />
              <p className='text-white mt-2'>{p.label}</p>
            </button>
          ))}
        </div>
        {errors.programaId && <p className='text-red-400 text-sm mt-1'>{errors.programaId}</p>}
      </div>
    </div>
  );
};
