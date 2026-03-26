import React from 'react';
import { Copy, Plus, Trash2 } from 'lucide-react';
import { StepProps, TipoPassageiro } from './types';

const inputClass = 'h-10 w-full rounded-lg border border-gray-300 text-sm px-3 focus:ring-2 focus:ring-blue-500 outline-none';
const labels: Record<TipoPassageiro, string> = { adulto: 'Adulto', crianca: 'Criança', bebe: 'Bebê' };

export const StepPassageiros: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const addPassenger = (tipo: TipoPassageiro) => {
    onUpdate({
      passageiros: [
        ...data.passageiros,
        { id: crypto.randomUUID(), tipo, nome: '', cpf: '', dataNascimento: '', rg: '', passaporte: '', validadePassaporte: '', observacoes: '' },
      ],
    });
  };

  return (
    <div className='space-y-6'>
      <h2 className='text-2xl font-semibold text-gray-900'>Passageiros</h2>

      <div className='flex flex-wrap gap-4'>
        <button type='button' className='bg-blue-600 text-white h-10 px-4 rounded-lg text-sm transition-all duration-200 hover:bg-blue-700 hover:shadow-md active:scale-95 inline-flex items-center gap-2' onClick={() => addPassenger('adulto')}><Plus size={16} />Adicionar Adulto</button>
        <button type='button' className='bg-blue-600 text-white h-10 px-4 rounded-lg text-sm transition-all duration-200 hover:bg-blue-700 hover:shadow-md active:scale-95 inline-flex items-center gap-2' onClick={() => addPassenger('crianca')}><Plus size={16} />Adicionar Criança</button>
        <button type='button' className='bg-blue-600 text-white h-10 px-4 rounded-lg text-sm transition-all duration-200 hover:bg-blue-700 hover:shadow-md active:scale-95 inline-flex items-center gap-2' onClick={() => addPassenger('bebe')}><Plus size={16} />Adicionar Bebê</button>
      </div>

      {errors.passageiros && <p className='text-xs text-red-500'>{errors.passageiros}</p>}

      {data.passageiros.map((p, idx) => (
        <div key={p.id} className='bg-white border border-gray-200 rounded-xl shadow-sm p-4 space-y-4'>
          <div className='flex items-center justify-between'>
            <p className='text-sm font-medium text-gray-900'>{labels[p.tipo]} #{idx + 1} {p.nome && `- ${p.nome}`}</p>
            <div className='flex gap-2'>
              <button type='button' className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95' onClick={() => onUpdate({ passageiros: [...data.passageiros, { ...p, id: crypto.randomUUID() }] })}><Copy size={14} /></button>
              <button type='button' className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95' onClick={() => onUpdate({ passageiros: data.passageiros.filter((row) => row.id !== p.id) })}><Trash2 size={14} /></button>
            </div>
          </div>

          <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
            <input className={`${inputClass} ${errors[`passageiroNome-${idx}`] ? 'border-red-500' : ''}`} placeholder='Nome completo' value={p.nome} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, nome: e.target.value }; onUpdate({ passageiros });
            }} />
            <input className={`${inputClass} ${errors[`passageiroCpf-${idx}`] ? 'border-red-500' : ''}`} placeholder='CPF' value={p.cpf} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, cpf: e.target.value }; onUpdate({ passageiros });
            }} />
            <input className={`${inputClass} ${errors[`passageiroNascimento-${idx}`] ? 'border-red-500' : ''}`} type='date' value={p.dataNascimento} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, dataNascimento: e.target.value }; onUpdate({ passageiros });
            }} />
            <input className={inputClass} placeholder='Passaporte (opcional)' value={p.passaporte} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, passaporte: e.target.value }; onUpdate({ passageiros });
            }} />
          </div>

          {(errors[`passageiroNome-${idx}`] || errors[`passageiroCpf-${idx}`] || errors[`passageiroNascimento-${idx}`] || errors[`passageiroTipo-${idx}`]) && (
            <p className='text-xs text-red-500'>{errors[`passageiroNome-${idx}`] || errors[`passageiroCpf-${idx}`] || errors[`passageiroNascimento-${idx}`] || errors[`passageiroTipo-${idx}`]}</p>
          )}
        </div>
      ))}
    </div>
  );
};
