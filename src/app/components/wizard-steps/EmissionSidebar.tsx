import React from 'react';
import { EmissionData } from './types';

interface Props {
  data: EmissionData;
  lastSavedAt: string;
}

export const EmissionSidebar: React.FC<Props> = ({ data, lastSavedAt }) => (
  <aside className='rounded-xl border border-gray-700 bg-gray-800 p-5 space-y-4'>
    <h3 className='text-xl font-semibold text-white'>Resumo da Emissão</h3>
    <div className='text-sm text-gray-300 space-y-1'>
      <p>Cliente: <span className='text-white'>{data.clienteId || '-'}</span></p>
      <p>Programa: <span className='text-white'>{data.programaId || '-'}</span></p>
      <p>Rota: <span className='text-white'>{data.vooIda.origem || '-'} → {data.vooIda.destino || '-'}</span></p>
      <p>Passageiros: <span className='text-white'>{data.passageiros.length}</span></p>
    </div>
    <div className='pt-3 border-t border-gray-700'>
      <p className='text-gray-400 text-sm'>Valor Total</p>
      <p className='text-3xl font-bold text-white'>R$ {data.valores.valorTotalFinal.toFixed(2)}</p>
      <p className='text-green-400 text-sm'>Lucro: R$ {data.valores.lucro.toFixed(2)}</p>
    </div>
    <p className='text-xs text-green-400'>● {lastSavedAt ? `Autossalvo ${lastSavedAt}` : 'Autossalvo ativo'}</p>
  </aside>
);
