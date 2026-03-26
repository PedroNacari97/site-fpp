import React from 'react';
import { Loader2 } from 'lucide-react';
import { EmissionData } from './types';

interface Props {
  data: EmissionData;
  loading: boolean;
  onEdit: (step: number) => void;
  onFinish: () => void;
}

export const StepRevisao: React.FC<Props> = ({ data, loading, onEdit, onFinish }) => {
  return (
    <div className='space-y-4'>
      <h2 className='text-2xl font-semibold text-white'>Revisão Final</h2>
      <div className='review-card'>
        <p className='text-white font-medium'>Cliente & Programa</p>
        <p className='text-gray-300'>{data.clienteId} • {data.programaId}</p>
        <button className='btn-outline' type='button' onClick={() => onEdit(1)}>Editar</button>
      </div>
      <div className='review-card'>
        <p className='text-white font-medium'>Rota</p>
        <p className='text-gray-300'>{data.vooIda.origem} → {data.vooIda.destino}</p>
        <button className='btn-outline' type='button' onClick={() => onEdit(2)}>Editar</button>
      </div>
      <div className='review-card'>
        <p className='text-white font-medium'>Passageiros</p>
        <p className='text-gray-300'>{data.passageiros.length} pessoa(s)</p>
        <button className='btn-outline' type='button' onClick={() => onEdit(4)}>Editar</button>
      </div>
      <div className='rounded-xl border border-green-500/40 bg-green-900/20 p-4 text-green-300'>Pronto para finalizar!</div>
      <button type='button' onClick={onFinish} className='btn bg-green-600 w-full' disabled={loading}>
        {loading ? <><Loader2 className='animate-spin' size={16} /> Salvando...</> : 'Finalizar Emissão'}
      </button>
    </div>
  );
};
