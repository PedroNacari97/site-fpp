import React from 'react';
import { Option, StepProps, TipoEmissao } from './types';

const TIPOS: Option[] = [
  { id: 'conta_cliente', label: 'Conta do Cliente', description: 'Cliente usa suas próprias milhas' },
  { id: 'conta_administradora', label: 'Conta Administradora', description: 'Empresa emite com conta administrada' },
  { id: 'emissor_parceiro', label: 'Emissor Parceiro', description: 'Emissão por terceiros' },
];

const PROGRAMAS: Option[] = [
  { id: 'latam', label: 'LATAM Pass', color: 'bg-red-500' },
  { id: 'smiles', label: 'Smiles', color: 'bg-orange-500' },
  { id: 'azul', label: 'TudoAzul', color: 'bg-blue-600' },
  { id: 'privilege', label: 'Privilege Club', color: 'bg-purple-500' },
];

const CLIENTES: Option[] = [
  { id: '1', label: 'João Silva - CPF 123.456.789-00' },
  { id: '2', label: 'Maria Souza - CPF 987.654.321-00' },
];

const inputClass = 'h-10 w-full rounded-lg border border-gray-300 text-sm px-3 focus:ring-2 focus:ring-blue-500 outline-none';

export const StepCliente: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  return (
    <div className='space-y-6'>
      <h2 className='text-2xl font-semibold text-gray-900'>Dados do Cliente</h2>

      <div className='space-y-2'>
        <label className='text-sm font-medium text-gray-900'>Tipo de emissão</label>
        <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
          {TIPOS.map((tipo) => (
            <button
              key={tipo.id}
              type='button'
              onClick={() => onUpdate({ tipoEmissao: tipo.id as TipoEmissao })}
              className={`p-4 rounded-xl border transition-all duration-200 hover:shadow-md active:scale-95 text-left ${
                data.tipoEmissao === tipo.id ? 'border-blue-600 bg-blue-50' : 'border-gray-200 bg-white'
              }`}
            >
              <p className='text-sm font-medium text-gray-900'>{tipo.label}</p>
              <p className='text-xs text-gray-500 mt-1'>{tipo.description}</p>
            </button>
          ))}
        </div>
        {errors.tipoEmissao && <p className='text-xs text-red-500'>{errors.tipoEmissao}</p>}
      </div>

      <div className='space-y-2'>
        <label className='text-sm font-medium text-gray-900'>Cliente</label>
        <select className={inputClass} value={data.clienteId} onChange={(e) => onUpdate({ clienteId: e.target.value })}>
          <option value=''>Selecione...</option>
          {CLIENTES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <p className='text-xs text-gray-500'>Ao selecionar um cliente, você pode reaproveitar passageiros frequentes.</p>
        {errors.clienteId && <p className='text-xs text-red-500'>{errors.clienteId}</p>}
      </div>

      <div className='space-y-2'>
        <label className='text-sm font-medium text-gray-900'>Programa</label>
        <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
          {PROGRAMAS.map((p) => (
            <button
              key={p.id}
              type='button'
              onClick={() => onUpdate({ programaId: p.id })}
              className={`p-4 rounded-xl border transition-all duration-200 hover:shadow-md active:scale-95 ${
                data.programaId === p.id ? 'border-blue-600 bg-blue-50' : 'border-gray-200 bg-white'
              }`}
            >
              <span className={`inline-block w-3 h-3 rounded-full ${p.color}`} />
              <p className='text-sm font-medium text-gray-900 mt-2'>{p.label}</p>
            </button>
          ))}
        </div>
        {errors.programaId && <p className='text-xs text-red-500'>{errors.programaId}</p>}
      </div>
    </div>
  );
};
