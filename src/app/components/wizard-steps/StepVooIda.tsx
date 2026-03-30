import React from 'react';
import { CalendarDays, MapPin, Plane, Plus, Trash2 } from 'lucide-react';
import { normalizeIata } from '../../utils/emissionValidation';
import {
  cn,
  fieldErrorClass,
  fieldHintClass,
  fieldLabelClass,
  inputClass,
  secondaryButtonClass,
} from './theme';
import { StepProps } from './types';

export const StepVooIda: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const voo = data.vooIda;
  const updateVoo = (patch: Partial<typeof voo>) => onUpdate({ vooIda: { ...voo, ...patch } });

  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <h2 className='text-[24px] font-semibold leading-8 text-white'>Voo de Ida</h2>
        <p className='text-base text-[#99a1af]'>Detalhe a rota principal da emissão</p>
      </div>

      <div className='grid gap-4 md:grid-cols-2'>
        <div className='space-y-2'>
          <label className={fieldLabelClass}>IATA Origem</label>
          <div className='relative'>
            <MapPin className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
            <input
              className={cn(inputClass, 'pl-11', errors.vooIdaOrigem && 'border-[#ef4444]')}
              value={voo.origem}
              placeholder='Ex.: GRU'
              onChange={(e) => updateVoo({ origem: normalizeIata(e.target.value) })}
            />
          </div>
        </div>

        <div className='space-y-2'>
          <label className={fieldLabelClass}>IATA Destino</label>
          <div className='relative'>
            <MapPin className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
            <input
              className={cn(inputClass, 'pl-11', errors.vooIdaDestino && 'border-[#ef4444]')}
              value={voo.destino}
              placeholder='Ex.: LIS'
              onChange={(e) => updateVoo({ destino: normalizeIata(e.target.value) })}
            />
          </div>
        </div>
      </div>

      {(errors.vooIdaOrigem || errors.vooIdaDestino || errors.vooIdaRota) && (
        <p className={fieldErrorClass}>{errors.vooIdaOrigem || errors.vooIdaDestino || errors.vooIdaRota}</p>
      )}

      <div className='rounded-[12px] border border-[#364153] bg-[#101828] p-5'>
        <div className='flex flex-col items-center justify-between gap-4 text-center sm:flex-row sm:text-left'>
          <div>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Origem</p>
            <p className='mt-2 text-[28px] font-semibold text-white'>{voo.origem || '---'}</p>
          </div>
          <div className='flex h-11 w-11 items-center justify-center rounded-full bg-[#1e2939] text-[#155dfc]'>
            <Plane size={20} />
          </div>
          <div>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Destino</p>
            <p className='mt-2 text-[28px] font-semibold text-white'>{voo.destino || '---'}</p>
          </div>
        </div>
      </div>

      <div className='grid gap-4 md:grid-cols-2'>
        <div className='space-y-2'>
          <label className={fieldLabelClass}>Companhia</label>
          <input
            className={cn(inputClass, errors.vooIdaCompanhia && 'border-[#ef4444]')}
            value={voo.companhia}
            placeholder='Ex.: LATAM'
            onChange={(e) => updateVoo({ companhia: e.target.value })}
          />
        </div>

        <div className='space-y-2'>
          <label className={fieldLabelClass}>Data e Hora</label>
          <div className='relative'>
            <CalendarDays className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
            <input
              className={cn(inputClass, 'pl-11', errors.vooIdaDataHora && 'border-[#ef4444]')}
              type='datetime-local'
              value={voo.dataHora}
              onChange={(e) => updateVoo({ dataHora: e.target.value })}
            />
          </div>
        </div>
      </div>

      <label className='flex items-center gap-3 rounded-[12px] border border-[#364153] bg-[#101828] px-4 py-3 text-sm text-[#d1d5dc]'>
        <input
          type='checkbox'
          className='h-4 w-4 accent-[#155dfc]'
          checked={voo.possuiEscala}
          onChange={(e) => updateVoo({ possuiEscala: e.target.checked, escalas: e.target.checked ? voo.escalas : [] })}
        />
        Este voo possui escala?
      </label>

      {voo.possuiEscala && (
        <div className='space-y-4'>
          <div className='flex items-center justify-between'>
            <div>
              <p className='text-sm font-medium text-[#d1d5dc]'>Escalas</p>
              <p className={fieldHintClass}>Adicione os trechos intermediários do voo principal</p>
            </div>
            <button
              type='button'
              className={secondaryButtonClass}
              onClick={() =>
                updateVoo({
                  escalas: [...voo.escalas, { id: crypto.randomUUID(), iata: '', companhia: '', horario: '' }],
                })
              }
            >
              <Plus size={16} />
              Adicionar Escala
            </button>
          </div>

          {voo.escalas.map((escala, idx) => (
            <div key={escala.id} className='rounded-[12px] border border-[#364153] bg-[#101828] p-4'>
              <div className='grid gap-4 lg:grid-cols-[1fr_1fr_1fr_auto]'>
                <input
                  className={inputClass}
                  placeholder='IATA'
                  value={escala.iata}
                  onChange={(e) => {
                    const escalas = [...voo.escalas];
                    escalas[idx] = { ...escala, iata: normalizeIata(e.target.value) };
                    updateVoo({ escalas });
                  }}
                />
                <input
                  className={inputClass}
                  placeholder='Companhia'
                  value={escala.companhia}
                  onChange={(e) => {
                    const escalas = [...voo.escalas];
                    escalas[idx] = { ...escala, companhia: e.target.value };
                    updateVoo({ escalas });
                  }}
                />
                <input
                  className={inputClass}
                  type='time'
                  value={escala.horario}
                  onChange={(e) => {
                    const escalas = [...voo.escalas];
                    escalas[idx] = { ...escala, horario: e.target.value };
                    updateVoo({ escalas });
                  }}
                />
                <button
                  type='button'
                  className={secondaryButtonClass}
                  onClick={() => updateVoo({ escalas: voo.escalas.filter((_, i) => i !== idx) })}
                >
                  <Trash2 size={16} />
                  Remover
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
