import React from 'react';
import { EmissionData } from './types';

interface Props {
  data: EmissionData;
  lastSavedAt: string;
}

export const EmissionSidebar: React.FC<Props> = ({ data, lastSavedAt }) => (
  <aside className='sticky top-6 bg-white border border-gray-200 rounded-xl shadow-sm p-6 h-full space-y-6'>
    <h3 className='text-lg font-medium text-gray-900'>Resumo da Emissão</h3>

    <div className='space-y-3 text-sm'>
      <div>
        <p className='text-gray-500 text-xs'>Cliente</p>
        <p className='text-gray-900'>{data.clienteId || '-'}</p>
      </div>
      <div>
        <p className='text-gray-500 text-xs'>Programa</p>
        <p className='text-gray-900'>{data.programaId || '-'}</p>
      </div>
      <div>
        <p className='text-gray-500 text-xs'>Rota</p>
        <p className='text-gray-900'>{data.vooIda.origem || '-'} → {data.vooIda.destino || '-'}</p>
      </div>
      <div>
        <p className='text-gray-500 text-xs'>Passageiros</p>
        <p className='text-gray-900'>{data.passageiros.length} pessoa(s)</p>
      </div>
    </div>

    <div className='border-t border-gray-200 pt-4'>
      <p className='text-xs text-gray-500'>Valor Total</p>
      <p className='text-2xl font-semibold text-gray-900'>R$ {data.valores.valorTotalFinal.toFixed(2)}</p>
      <p className='text-sm text-green-500'>Lucro: R$ {data.valores.lucro.toFixed(2)}</p>
    </div>

    <p className='text-xs text-gray-500'>● {lastSavedAt ? `Autossalvo às ${lastSavedAt}` : 'Autossalvo ativo'}</p>
  </aside>
);
