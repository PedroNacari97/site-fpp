import React from 'react';
import { StepProps } from './types';
import { normalizeIata } from '../../utils/emissionValidation';

const inputClass = 'h-10 w-full rounded-lg border border-gray-300 text-sm px-3 focus:ring-2 focus:ring-blue-500 outline-none';

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
      <h2 className='text-2xl font-semibold text-gray-900'>Voo de Volta</h2>

      <label className='inline-flex items-center gap-2 text-sm font-medium text-gray-900'>
        <input type='checkbox' checked={data.possuiVolta} onChange={(e) => onUpdate({ possuiVolta: e.target.checked })} />
        Esta emissão possui voo de volta?
      </label>

      {!data.possuiVolta ? (
        <div className='p-4 rounded-xl border border-gray-200 bg-white text-sm text-gray-500'>One-way ativo.</div>
      ) : (
        <>
          <button type='button' className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95' onClick={invertRoute}>Inverter Rota</button>
          <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
            <input className={`${inputClass} ${errors.vooVoltaOrigem ? 'border-red-500' : ''}`} placeholder='IATA Origem' value={voo.origem} onChange={(e) => updateVoo({ origem: normalizeIata(e.target.value) })} />
            <input className={`${inputClass} ${errors.vooVoltaDestino ? 'border-red-500' : ''}`} placeholder='IATA Destino' value={voo.destino} onChange={(e) => updateVoo({ destino: normalizeIata(e.target.value) })} />
            <input className={`${inputClass} ${errors.vooVoltaCompanhia ? 'border-red-500' : ''}`} placeholder='Companhia' value={voo.companhia} onChange={(e) => updateVoo({ companhia: e.target.value })} />
            <input className={`${inputClass} ${errors.vooVoltaDataHora ? 'border-red-500' : ''}`} type='datetime-local' value={voo.dataHora} onChange={(e) => updateVoo({ dataHora: e.target.value })} />
          </div>
        </>
      )}
    </div>
  );
};
