import React from 'react';
import { StepProps } from './types';
import { normalizeIata } from '../../utils/emissionValidation';

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
    <div className='space-y-4'>
      <h2 className='text-2xl font-semibold text-white'>Voo de Volta</h2>
      <label className='inline-flex items-center gap-2 text-gray-200'>
        <input type='checkbox' checked={data.possuiVolta} onChange={(e) => onUpdate({ possuiVolta: e.target.checked })} />
        Esta emissão possui voo de volta?
      </label>

      {!data.possuiVolta ? (
        <div className='rounded-lg border border-blue-500/30 bg-blue-900/20 p-4 text-blue-300'>One-way habilitado</div>
      ) : (
        <>
          <button type='button' className='btn-outline' onClick={invertRoute}>Inverter Rota</button>
          <div className='grid md:grid-cols-2 gap-4'>
            <input className='input' placeholder='IATA Origem' value={voo.origem} onChange={(e) => updateVoo({ origem: normalizeIata(e.target.value) })} />
            <input className='input' placeholder='IATA Destino' value={voo.destino} onChange={(e) => updateVoo({ destino: normalizeIata(e.target.value) })} />
            <input className='input' placeholder='Companhia aérea' value={voo.companhia} onChange={(e) => updateVoo({ companhia: e.target.value })} />
            <input className='input' type='datetime-local' value={voo.dataHora} onChange={(e) => updateVoo({ dataHora: e.target.value })} />
          </div>
          {(errors.vooVoltaOrigem || errors.vooVoltaDestino || errors.vooVoltaCompanhia || errors.vooVoltaDataHora) && <p className='text-red-400 text-sm'>{errors.vooVoltaOrigem || errors.vooVoltaDestino || errors.vooVoltaCompanhia || errors.vooVoltaDataHora}</p>}
        </>
      )}
    </div>
  );
};
