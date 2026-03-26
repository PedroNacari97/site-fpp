import React from 'react';
import { Plane, Plus, Trash2 } from 'lucide-react';
import { StepProps } from './types';
import { normalizeIata } from '../../utils/emissionValidation';

const inputClass = 'h-10 w-full rounded-lg border border-gray-300 text-sm px-3 focus:ring-2 focus:ring-blue-500 outline-none';

export const StepVooIda: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const voo = data.vooIda;
  const updateVoo = (patch: Partial<typeof voo>) => onUpdate({ vooIda: { ...voo, ...patch } });

  return (
    <div className='space-y-6'>
      <h2 className='text-2xl font-semibold text-gray-900'>Voo de Ida</h2>

      <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
        <div className='space-y-1'>
          <label className='text-sm font-medium text-gray-900'>IATA Origem</label>
          <input className={`${inputClass} ${errors.vooIdaOrigem ? 'border-red-500' : ''}`} value={voo.origem} onChange={(e) => updateVoo({ origem: normalizeIata(e.target.value) })} />
        </div>
        <div className='space-y-1'>
          <label className='text-sm font-medium text-gray-900'>IATA Destino</label>
          <input className={`${inputClass} ${errors.vooIdaDestino ? 'border-red-500' : ''}`} value={voo.destino} onChange={(e) => updateVoo({ destino: normalizeIata(e.target.value) })} />
        </div>
      </div>
      {(errors.vooIdaOrigem || errors.vooIdaDestino || errors.vooIdaRota) && <p className='text-xs text-red-500'>{errors.vooIdaOrigem || errors.vooIdaDestino || errors.vooIdaRota}</p>}

      {voo.origem && voo.destino && (
        <div className='p-4 border border-gray-200 rounded-xl shadow-sm bg-white flex items-center justify-between'>
          <span className='text-lg font-medium'>{voo.origem}</span>
          <Plane className='text-blue-600' size={16} />
          <span className='text-lg font-medium'>{voo.destino}</span>
        </div>
      )}

      <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
        <div className='space-y-1'>
          <label className='text-sm font-medium text-gray-900'>Companhia</label>
          <input className={`${inputClass} ${errors.vooIdaCompanhia ? 'border-red-500' : ''}`} value={voo.companhia} onChange={(e) => updateVoo({ companhia: e.target.value })} />
        </div>
        <div className='space-y-1'>
          <label className='text-sm font-medium text-gray-900'>Data e Hora</label>
          <input className={`${inputClass} ${errors.vooIdaDataHora ? 'border-red-500' : ''}`} type='datetime-local' value={voo.dataHora} onChange={(e) => updateVoo({ dataHora: e.target.value })} />
        </div>
      </div>

      <label className='inline-flex items-center gap-2 text-sm font-medium text-gray-900'>
        <input type='checkbox' checked={voo.possuiEscala} onChange={(e) => updateVoo({ possuiEscala: e.target.checked, escalas: e.target.checked ? voo.escalas : [] })} />
        Este voo possui escala?
      </label>

      {voo.possuiEscala && (
        <div className='space-y-4'>
          {voo.escalas.map((escala, idx) => (
            <div key={escala.id} className='grid grid-cols-1 md:grid-cols-4 gap-4'>
              <input className={inputClass} placeholder='IATA' value={escala.iata} onChange={(e) => {
                const escalas = [...voo.escalas];
                escalas[idx] = { ...escala, iata: normalizeIata(e.target.value) };
                updateVoo({ escalas });
              }} />
              <input className={inputClass} placeholder='Companhia' value={escala.companhia} onChange={(e) => {
                const escalas = [...voo.escalas];
                escalas[idx] = { ...escala, companhia: e.target.value };
                updateVoo({ escalas });
              }} />
              <input className={inputClass} type='time' value={escala.horario} onChange={(e) => {
                const escalas = [...voo.escalas];
                escalas[idx] = { ...escala, horario: e.target.value };
                updateVoo({ escalas });
              }} />
              <button type='button' className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95' onClick={() => updateVoo({ escalas: voo.escalas.filter((_, i) => i !== idx) })}><Trash2 size={16} /></button>
            </div>
          ))}
          <button type='button' className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95 inline-flex items-center gap-2' onClick={() => updateVoo({ escalas: [...voo.escalas, { id: crypto.randomUUID(), iata: '', companhia: '', horario: '' }] })}><Plus size={16} /> Adicionar Escala</button>
        </div>
      )}
    </div>
  );
};
