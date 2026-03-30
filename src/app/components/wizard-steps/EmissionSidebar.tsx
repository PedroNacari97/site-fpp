import React from 'react';
import { getClientLabel, getPassengerSummary, getProgramLabel, innerPanelClass, surfaceCardClass } from './theme';
import { EmissionData } from './types';

interface Props {
  data: EmissionData;
  lastSavedAt: string;
}

export const EmissionSidebar: React.FC<Props> = ({ data, lastSavedAt }) => {
  const passengerSummary = getPassengerSummary(data);

  return (
    <aside className={`sticky top-6 space-y-5 self-start p-6 ${surfaceCardClass}`}>
      <h3 className='text-lg font-semibold text-white'>Resumo da Emissão</h3>

      <div className='space-y-3 text-sm'>
        <div className={`${innerPanelClass} p-4`}>
          <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Cliente</p>
          <p className='mt-2 text-sm text-[#d1d5dc]'>{getClientLabel(data.clienteId)}</p>
        </div>

        <div className={`${innerPanelClass} p-4`}>
          <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Programa</p>
          <p className='mt-2 text-sm text-[#d1d5dc]'>{getProgramLabel(data.programaId)}</p>
        </div>

        <div className={`${innerPanelClass} p-4`}>
          <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Rota</p>
          <p className='mt-2 text-sm text-[#d1d5dc]'>
            {data.vooIda.origem || '-'} → {data.vooIda.destino || '-'}
          </p>
        </div>

        <div className={`${innerPanelClass} p-4`}>
          <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Passageiros</p>
          <p className='mt-2 text-sm text-[#d1d5dc]'>{passengerSummary.label}</p>
        </div>
      </div>

      <div className='border-t border-[#364153] pt-5'>
        <div className='flex items-center gap-3 text-xs text-[#99a1af]'>
          <span className='inline-block h-2 w-2 rounded-full bg-[#00c950]' />
          {lastSavedAt ? `Autossalvo às ${lastSavedAt}` : 'Autossalvo agora'}
        </div>
      </div>
    </aside>
  );
};
