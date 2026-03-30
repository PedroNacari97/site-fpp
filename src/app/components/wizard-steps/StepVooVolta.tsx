import React from 'react';
import { ArrowRightLeft, CalendarDays, MapPin } from 'lucide-react';
import { normalizeIata } from '../../utils/emissionValidation';
import { cn, fieldLabelClass, inputClass, secondaryButtonClass } from './theme';
import { StepProps } from './types';

export const StepVooVolta: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const voo = data.vooVolta;
  const updateVoo = (patch: Partial<typeof voo>) => onUpdate({ vooVolta: { ...voo, ...patch } });

  const invertRoute = () => {
    onUpdate({
      vooVolta: {
        ...voo,
        origem: data.vooIda.destino,
        destino: data.vooIda.origem,
        companhia: data.vooIda.companhia,
      },
    });
  };

  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <h2 className='text-[24px] font-semibold leading-8 text-white'>Voo de Volta</h2>
        <p className='text-base text-[#99a1af]'>Configure o retorno apenas se a emissão tiver trecho de volta</p>
      </div>

      <label className='flex items-center gap-3 rounded-[12px] border border-[#364153] bg-[#101828] px-4 py-3 text-sm text-[#d1d5dc]'>
        <input
          type='checkbox'
          className='h-4 w-4 accent-[#155dfc]'
          checked={data.possuiVolta}
          onChange={(e) => onUpdate({ possuiVolta: e.target.checked })}
        />
        Esta emissão possui voo de volta?
      </label>

      {!data.possuiVolta ? (
        <div className='rounded-[12px] border border-dashed border-[#364153] bg-[#101828] px-5 py-6 text-sm text-[#99a1af]'>
          One-way ativo. Se houver retorno, habilite o voo de volta para preencher esse trecho.
        </div>
      ) : (
        <>
          <div className='flex justify-start'>
            <button type='button' className={secondaryButtonClass} onClick={invertRoute}>
              <ArrowRightLeft size={16} />
              Inverter rota da ida
            </button>
          </div>

          <div className='grid gap-4 md:grid-cols-2'>
            <div className='space-y-2'>
              <label className={fieldLabelClass}>IATA Origem</label>
              <div className='relative'>
                <MapPin className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
                <input
                  className={cn(inputClass, 'pl-11', errors.vooVoltaOrigem && 'border-[#ef4444]')}
                  value={voo.origem}
                  placeholder='Ex.: LIS'
                  onChange={(e) => updateVoo({ origem: normalizeIata(e.target.value) })}
                />
              </div>
            </div>

            <div className='space-y-2'>
              <label className={fieldLabelClass}>IATA Destino</label>
              <div className='relative'>
                <MapPin className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
                <input
                  className={cn(inputClass, 'pl-11', errors.vooVoltaDestino && 'border-[#ef4444]')}
                  value={voo.destino}
                  placeholder='Ex.: GRU'
                  onChange={(e) => updateVoo({ destino: normalizeIata(e.target.value) })}
                />
              </div>
            </div>

            <div className='space-y-2'>
              <label className={fieldLabelClass}>Companhia</label>
              <input
                className={cn(inputClass, errors.vooVoltaCompanhia && 'border-[#ef4444]')}
                value={voo.companhia}
                placeholder='Ex.: TAP'
                onChange={(e) => updateVoo({ companhia: e.target.value })}
              />
            </div>

            <div className='space-y-2'>
              <label className={fieldLabelClass}>Data e Hora</label>
              <div className='relative'>
                <CalendarDays className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
                <input
                  className={cn(inputClass, 'pl-11', errors.vooVoltaDataHora && 'border-[#ef4444]')}
                  type='datetime-local'
                  value={voo.dataHora}
                  onChange={(e) => updateVoo({ dataHora: e.target.value })}
                />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
