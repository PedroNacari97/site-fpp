import React from 'react';
import { Copy, Plus, Trash2 } from 'lucide-react';
import { StepProps, TipoPassageiro } from './types';

const labels: Record<TipoPassageiro, string> = { adulto: 'Adulto', crianca: 'Criança', bebe: 'Bebê' };

export const StepPassageiros: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const addPassenger = (tipo: TipoPassageiro) => {
    onUpdate({
      passageiros: [...data.passageiros, {
        id: crypto.randomUUID(),
        tipo,
        nome: '', cpf: '', dataNascimento: '', observacoes: '', rg: '', passaporte: '', validadePassaporte: ''
      }],
    });
  };

  return (
    <div className='space-y-4'>
      <h2 className='text-2xl font-semibold text-white'>Passageiros</h2>
      <div className='flex gap-2'>
        <button type='button' className='btn' onClick={() => addPassenger('adulto')}><Plus size={16} />Adicionar Adulto</button>
        <button type='button' className='btn bg-green-600' onClick={() => addPassenger('crianca')}><Plus size={16} />Adicionar Criança</button>
        <button type='button' className='btn bg-purple-600' onClick={() => addPassenger('bebe')}><Plus size={16} />Adicionar Bebê</button>
      </div>

      {errors.passageiros && <p className='text-red-400'>{errors.passageiros}</p>}
      {data.passageiros.map((p, idx) => (
        <div key={p.id} className='rounded-xl border border-gray-700 p-4 bg-gray-900/60 space-y-3'>
          <div className='flex justify-between'>
            <p className='text-white'><span className='text-blue-400'>{labels[p.tipo]} #{idx + 1}</span> {p.nome}</p>
            <div className='flex gap-2'>
              <button type='button' className='btn-outline' onClick={() => onUpdate({ passageiros: [...data.passageiros, { ...p, id: crypto.randomUUID() }] })}><Copy size={14} /></button>
              <button type='button' className='btn-outline' onClick={() => onUpdate({ passageiros: data.passageiros.filter((item) => item.id !== p.id) })}><Trash2 size={14} /></button>
            </div>
          </div>

          <div className='grid md:grid-cols-2 gap-3'>
            <input className='input' placeholder='Nome completo' value={p.nome} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, nome: e.target.value }; onUpdate({ passageiros });
            }} />
            <input className='input' placeholder='CPF' value={p.cpf} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, cpf: e.target.value }; onUpdate({ passageiros });
            }} />
            <input className='input' type='date' placeholder='Nascimento' value={p.dataNascimento} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, dataNascimento: e.target.value }; onUpdate({ passageiros });
            }} />
            <input className='input' placeholder='Passaporte (opcional)' value={p.passaporte} onChange={(e) => {
              const passageiros = [...data.passageiros]; passageiros[idx] = { ...p, passaporte: e.target.value }; onUpdate({ passageiros });
            }} />
          </div>
          {(errors[`passageiroNome-${idx}`] || errors[`passageiroCpf-${idx}`] || errors[`passageiroNascimento-${idx}`] || errors[`passageiroTipo-${idx}`]) && (
            <p className='text-red-400 text-sm'>{errors[`passageiroNome-${idx}`] || errors[`passageiroCpf-${idx}`] || errors[`passageiroNascimento-${idx}`] || errors[`passageiroTipo-${idx}`]}</p>
          )}
        </div>
      ))}
    </div>
  );
};
