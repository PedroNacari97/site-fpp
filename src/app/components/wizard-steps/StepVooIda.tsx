import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { StepProps } from './types';
import { normalizeIata } from '../../utils/emissionValidation';

export const StepVooIda: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const voo = data.vooIda;

  const updateVoo = (patch: Partial<typeof voo>) => onUpdate({ vooIda: { ...voo, ...patch } });

  return (
    <div className='space-y-5'>
      <h2 className='text-2xl font-semibold text-white'>Voo de Ida</h2>
      <div className='grid md:grid-cols-2 gap-4'>
        <input className='input' placeholder='IATA Origem' value={voo.origem} onChange={(e) => updateVoo({ origem: normalizeIata(e.target.value) })} />
        <input className='input' placeholder='IATA Destino' value={voo.destino} onChange={(e) => updateVoo({ destino: normalizeIata(e.target.value) })} />
      </div>
      {(errors.vooIdaOrigem || errors.vooIdaDestino || errors.vooIdaRota) && <p className='text-red-400 text-sm'>{errors.vooIdaOrigem || errors.vooIdaDestino || errors.vooIdaRota}</p>}

      {voo.origem && voo.destino && (
        <div className='rounded-xl border border-blue-500/40 bg-gradient-to-r from-blue-900/60 to-purple-900/60 p-4 text-white font-semibold'>
          {voo.origem} → {voo.destino}
        </div>
      )}

      <div className='grid md:grid-cols-2 gap-4'>
        <input className='input' placeholder='Companhia aérea' value={voo.companhia} onChange={(e) => updateVoo({ companhia: e.target.value })} />
        <input className='input' type='datetime-local' value={voo.dataHora} onChange={(e) => updateVoo({ dataHora: e.target.value })} />
      </div>
      {(errors.vooIdaCompanhia || errors.vooIdaDataHora) && <p className='text-red-400 text-sm'>{errors.vooIdaCompanhia || errors.vooIdaDataHora}</p>}

      <label className='inline-flex items-center gap-2 text-gray-200'>
        <input type='checkbox' checked={voo.possuiEscala} onChange={(e) => updateVoo({ possuiEscala: e.target.checked, escalas: e.target.checked ? voo.escalas : [] })} />
        Este voo possui escalas?
      </label>

      {voo.possuiEscala && (
        <div className='space-y-3'>
          {voo.escalas.map((escala, idx) => (
            <div key={escala.id} className='grid md:grid-cols-4 gap-2 items-center'>
              <input className='input' placeholder='IATA' value={escala.iata} onChange={(e) => {
                const escalas = [...voo.escalas];
                escalas[idx] = { ...escala, iata: normalizeIata(e.target.value) };
                updateVoo({ escalas });
              }} />
              <input className='input' placeholder='Companhia' value={escala.companhia} onChange={(e) => {
                const escalas = [...voo.escalas];
                escalas[idx] = { ...escala, companhia: e.target.value };
                updateVoo({ escalas });
              }} />
              <input className='input' type='time' value={escala.horario} onChange={(e) => {
                const escalas = [...voo.escalas];
                escalas[idx] = { ...escala, horario: e.target.value };
                updateVoo({ escalas });
              }} />
              <button type='button' className='btn-outline' onClick={() => updateVoo({ escalas: voo.escalas.filter((_, i) => i !== idx) })}><Trash2 size={16} /></button>
            </div>
          ))}
          <button type='button' className='btn-outline' onClick={() => updateVoo({ escalas: [...voo.escalas, { id: crypto.randomUUID(), iata: '', companhia: '', horario: '' }] })}><Plus size={16} /> Adicionar Escala</button>
          {Object.keys(errors).some((k) => k.startsWith('vooIdaEscala')) && <p className='text-red-400 text-sm'>Complete os dados das escalas.</p>}
        </div>
      )}
    </div>
  );
};
