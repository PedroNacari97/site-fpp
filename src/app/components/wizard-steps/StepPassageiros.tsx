import React from 'react';
import { Copy, Plus, Trash2, Users } from 'lucide-react';
import {
  cn,
  fieldErrorClass,
  fieldLabelClass,
  inputClass,
  passengerTypeLabels,
  secondaryButtonClass,
} from './theme';
import { StepProps, TipoPassageiro } from './types';

const addButtons: Array<{ tipo: TipoPassageiro; className: string; label: string }> = [
  { tipo: 'adulto', label: 'Adicionar Adulto', className: 'bg-[#155dfc] hover:bg-[#0f4ee8]' },
  { tipo: 'crianca', label: 'Adicionar Criança', className: 'bg-[#00c950] hover:bg-[#00b347]' },
  { tipo: 'bebe', label: 'Adicionar Bebê', className: 'bg-[#a855f7] hover:bg-[#9333ea]' },
];

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
      <div className='space-y-2'>
        <h2 className='text-[24px] font-semibold leading-8 text-white'>Passageiros</h2>
        <p className='text-base text-[#99a1af]'>Cadastre os viajantes e replique dados quando necessário</p>
      </div>

      <div className='flex flex-wrap gap-3'>
        {addButtons.map((button) => (
          <button
            key={button.tipo}
            type='button'
            className={cn(
              'inline-flex h-10 items-center gap-2 rounded-[10px] px-4 text-sm font-medium text-white transition',
              button.className,
            )}
            onClick={() => addPassenger(button.tipo)}
          >
            <Plus size={16} />
            {button.label}
          </button>
        ))}
      </div>

      {errors.passageiros && <p className={fieldErrorClass}>{errors.passageiros}</p>}

      {data.passageiros.length === 0 ? (
        <div className='rounded-[12px] border border-dashed border-[#364153] bg-[#101828] px-6 py-10 text-center'>
          <div className='mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#1e2939] text-[#99a1af]'>
            <Users size={20} />
          </div>
          <p className='mt-4 text-base font-medium text-[#d1d5dc]'>Nenhum passageiro adicionado</p>
          <p className='mt-2 text-sm text-[#6a7282]'>Use os botões acima para começar a montar a lista de viajantes.</p>
        </div>
      ) : (
        data.passageiros.map((p, idx) => (
          <div key={p.id} className='rounded-[12px] border border-[#364153] bg-[#101828] p-5'>
            <div className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
              <div>
                <p className='text-sm font-medium text-white'>
                  {passengerTypeLabels[p.tipo]} #{idx + 1} {p.nome && `• ${p.nome}`}
                </p>
                <p className='mt-1 text-xs text-[#6a7282]'>Preencha os dados obrigatórios para validação da emissão.</p>
              </div>

              <div className='flex gap-2'>
                <button
                  type='button'
                  className={secondaryButtonClass}
                  onClick={() => onUpdate({ passageiros: [...data.passageiros, { ...p, id: crypto.randomUUID() }] })}
                >
                  <Copy size={16} />
                  Duplicar
                </button>
                <button
                  type='button'
                  className={secondaryButtonClass}
                  onClick={() => onUpdate({ passageiros: data.passageiros.filter((row) => row.id !== p.id) })}
                >
                  <Trash2 size={16} />
                  Remover
                </button>
              </div>
            </div>

            <div className='mt-5 grid gap-4 md:grid-cols-2'>
              <div className='space-y-2'>
                <label className={fieldLabelClass}>Nome completo</label>
                <input
                  className={cn(inputClass, errors[`passageiroNome-${idx}`] && 'border-[#ef4444]')}
                  value={p.nome}
                  onChange={(e) => {
                    const passageiros = [...data.passageiros];
                    passageiros[idx] = { ...p, nome: e.target.value };
                    onUpdate({ passageiros });
                  }}
                />
              </div>

              <div className='space-y-2'>
                <label className={fieldLabelClass}>CPF</label>
                <input
                  className={cn(inputClass, errors[`passageiroCpf-${idx}`] && 'border-[#ef4444]')}
                  value={p.cpf}
                  onChange={(e) => {
                    const passageiros = [...data.passageiros];
                    passageiros[idx] = { ...p, cpf: e.target.value };
                    onUpdate({ passageiros });
                  }}
                />
              </div>

              <div className='space-y-2'>
                <label className={fieldLabelClass}>Data de nascimento</label>
                <input
                  className={cn(inputClass, errors[`passageiroNascimento-${idx}`] && 'border-[#ef4444]')}
                  type='date'
                  value={p.dataNascimento}
                  onChange={(e) => {
                    const passageiros = [...data.passageiros];
                    passageiros[idx] = { ...p, dataNascimento: e.target.value };
                    onUpdate({ passageiros });
                  }}
                />
              </div>

              <div className='space-y-2'>
                <label className={fieldLabelClass}>Passaporte</label>
                <input
                  className={inputClass}
                  value={p.passaporte}
                  placeholder='Opcional'
                  onChange={(e) => {
                    const passageiros = [...data.passageiros];
                    passageiros[idx] = { ...p, passaporte: e.target.value };
                    onUpdate({ passageiros });
                  }}
                />
              </div>
            </div>

            {(errors[`passageiroNome-${idx}`] ||
              errors[`passageiroCpf-${idx}`] ||
              errors[`passageiroNascimento-${idx}`] ||
              errors[`passageiroTipo-${idx}`]) && (
              <p className='mt-4 text-xs text-[#f87171]'>
                {errors[`passageiroNome-${idx}`] ||
                  errors[`passageiroCpf-${idx}`] ||
                  errors[`passageiroNascimento-${idx}`] ||
                  errors[`passageiroTipo-${idx}`]}
              </p>
            )}
          </div>
        ))
      )}
    </div>
  );
};
