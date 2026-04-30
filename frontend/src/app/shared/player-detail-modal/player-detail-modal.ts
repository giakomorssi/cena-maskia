import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

export type PlayerDetailData = {
  playerName: string;
  ownerTeamName: string;
  role: string;
  contractType: string;
  marketValue: number;
  salary: number;
  fascia: string;
  contractYearsTotal: number;
  contractYearsRemaining: number;
  sourceLabel?: string | null;
  amount?: number | null;
};

@Component({
  selector: 'app-player-detail-modal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './player-detail-modal.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerDetailModalComponent {
  @Input({ required: true }) player!: PlayerDetailData;
  @Output() close = new EventEmitter<void>();

  onClose() {
    this.close.emit();
  }
}
