import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { LeagueApi } from '../../services/league.api';
import { MarkdownPipe } from '../../shared/markdown.pipe';

interface RegulationSection {
  id: string;
  title: string;
  body: string;
}

interface PdfTextToken {
  text: string;
  style: 'normal' | 'bold';
}

interface PdfLinePart {
  text: string;
  style: 'normal' | 'bold';
}

@Component({
  selector: 'app-regolamento',
  imports: [MarkdownPipe],
  templateUrl: './regolamento.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegolamentoComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  title = signal('Regolamento');
  body = signal<string>('');
  sections = signal<RegulationSection[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  exporting = signal(false);

  ngOnInit() {
    this.api.getContent('regolamento').subscribe({
      next: (r) => {
        const markdown = r.body_md ?? '';
        this.body.set(markdown);
        this.parseMarkdown(markdown);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Impossibile caricare il regolamento');
        this.loading.set(false);
      },
    });
  }

  scrollToSection(sectionId: string) {
    const target = document.getElementById(sectionId);
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    history.replaceState(null, '', `#${sectionId}`);
  }

  async exportPdf() {
    const sections = this.sections();
    if (!sections.length) {
      return;
    }

    this.exporting.set(true);
    try {
      const { jsPDF } = await import('jspdf');
      const pdf = new jsPDF({
        orientation: 'p',
        unit: 'mm',
        format: 'a4',
      });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 16;
      const contentWidth = pageWidth - margin * 2;
      const lineHeight = 6;
      let cursorY = margin;

      const ensureSpace = (requiredHeight: number) => {
        if (cursorY + requiredHeight <= pageHeight - margin) {
          return;
        }
        pdf.addPage();
        cursorY = margin;
      };

      const sanitizePdfText = (text: string) =>
        text
          .replace(/→/g, ' -> ')
          .replace(/[–—]/g, '-')
          .replace(/[“”]/g, '"')
          .replace(/[‘’]/g, "'")
          .replace(/\u00a0/g, ' ');

      const parseInlineMarkdown = (
        text: string,
        defaultStyle: 'normal' | 'bold' = 'normal',
      ): PdfTextToken[] => {
        const sanitized = sanitizePdfText(text).replace(/\s+/g, ' ').trim();
        if (!sanitized) {
          return [];
        }

        const tokens: PdfTextToken[] = [];
        const pattern = /\*\*(.+?)\*\*/g;
        let lastIndex = 0;

        for (const match of sanitized.matchAll(pattern)) {
          const matchIndex = match.index ?? 0;
          const before = sanitized.slice(lastIndex, matchIndex);
          if (before) {
            tokens.push({ text: before, style: defaultStyle });
          }

          const boldText = match[1]?.trim();
          if (boldText) {
            tokens.push({ text: boldText, style: 'bold' });
          }
          lastIndex = matchIndex + match[0].length;
        }

        const after = sanitized.slice(lastIndex);
        if (after) {
          tokens.push({ text: after, style: defaultStyle });
        }

        return tokens.length ? tokens : [{ text: sanitized, style: defaultStyle }];
      };

      const buildInlineLines = (
        tokens: PdfTextToken[],
        fontSize: number,
        maxWidth: number,
        fallbackStyle: 'normal' | 'bold',
      ): PdfLinePart[][] => {
        const lines: PdfLinePart[][] = [];
        let currentLine: PdfLinePart[] = [];
        let currentWidth = 0;

        const measure = (text: string, style: 'normal' | 'bold') => {
          pdf.setFont('helvetica', style);
          pdf.setFontSize(fontSize);
          return pdf.getTextWidth(text);
        };

        const pushLine = () => {
          if (currentLine.length) {
            lines.push(currentLine);
          }
          currentLine = [];
          currentWidth = 0;
        };

        for (const token of tokens) {
          const style = token.style || fallbackStyle;
          const parts = token.text.split(/(\s+)/).filter((part) => part.length > 0);

          for (const part of parts) {
            const isWhitespace = /^\s+$/.test(part);
            if (!currentLine.length && isWhitespace) {
              continue;
            }

            const partWidth = measure(part, style);
            if (!isWhitespace && currentWidth > 0 && currentWidth + partWidth > maxWidth) {
              pushLine();
            }

            if (!currentLine.length && isWhitespace) {
              continue;
            }

            const previous = currentLine.at(-1);
            if (previous && previous.style === style) {
              previous.text += part;
            } else {
              currentLine.push({ text: part, style });
            }
            currentWidth += partWidth;
          }
        }

        pushLine();
        return lines;
      };

      const renderInlineText = (
        tokens: PdfTextToken[],
        options?: {
          fontSize?: number;
          x?: number;
          width?: number;
          defaultStyle?: 'normal' | 'bold';
        },
      ) => {
        const fontSize = options?.fontSize ?? 11;
        const startX = options?.x ?? margin;
        const maxWidth = options?.width ?? contentWidth;
        const fallbackStyle = options?.defaultStyle ?? 'normal';

        if (!tokens.length) {
          cursorY += lineHeight * 0.5;
          return;
        }
        const lines = buildInlineLines(tokens, fontSize, maxWidth, fallbackStyle);
        ensureSpace(lines.length * lineHeight + 2);

        for (const lineParts of lines) {
          let cursorX = startX;
          for (const part of lineParts) {
            pdf.setFont('helvetica', part.style);
            pdf.setFontSize(fontSize);
            pdf.text(part.text, cursorX, cursorY);
            cursorX += pdf.getTextWidth(part.text);
          }
          cursorY += lineHeight;
        }

        cursorY += 2;
      };

      const addWrappedText = (text: string, fontSize = 11, style: 'normal' | 'bold' = 'normal') => {
        renderInlineText(parseInlineMarkdown(text, style), {
          fontSize,
          x: margin,
          width: contentWidth,
          defaultStyle: style,
        });
      };

      const addListItem = (text: string) => {
        const tokens = parseInlineMarkdown(text);
        if (!tokens.length) {
          return;
        }
        renderInlineText([{ text: '- ', style: 'normal' }, ...tokens], {
          fontSize: 11,
          x: margin + 2,
          width: contentWidth - 2,
        });
      };

      const addNumberedItem = (index: number, text: string) => {
        const tokens = parseInlineMarkdown(text);
        if (!tokens.length) {
          return;
        }
        const prefix = `${index}. `;
        renderInlineText([{ text: prefix, style: 'normal' }, ...tokens], {
          fontSize: 11,
          x: margin + 2,
          width: contentWidth - 2,
        });
      };

      const parseTableRow = (line: string) =>
        line
          .trim()
          .replace(/^\|/, '')
          .replace(/\|$/, '')
          .split('|')
          .map((cell) => cell.trim());

      const isMarkdownTableDivider = (line: string) => {
        const cells = parseTableRow(line);
        return (
          cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, '')))
        );
      };

      const renderTable = (header: string[], rows: string[][]) => {
        const colCount = Math.max(header.length, ...rows.map((row) => row.length));
        if (!colCount) {
          return;
        }

        const tableWidth = contentWidth;
        const colWidth = tableWidth / colCount;
        const cellPaddingX = 2;
        const cellPaddingTop = 4;
        const baseFontSize = 10;

        const normalizedHeader = Array.from(
          { length: colCount },
          (_, index) => header[index] ?? '',
        );
        const normalizedRows = rows.map((row) =>
          Array.from({ length: colCount }, (_, index) => row[index] ?? ''),
        );

        const drawRow = (cells: string[], isHeader: boolean) => {
          const cellLines = cells.map((cell) =>
            buildInlineLines(
              parseInlineMarkdown(cell, isHeader ? 'bold' : 'normal'),
              baseFontSize,
              colWidth - cellPaddingX * 2,
              isHeader ? 'bold' : 'normal',
            ),
          );
          const maxLines = Math.max(1, ...cellLines.map((lines) => Math.max(lines.length, 1)));
          const rowHeight = maxLines * 5 + cellPaddingTop * 2;
          ensureSpace(rowHeight + 2);

          let cellX = margin;
          for (let index = 0; index < cells.length; index++) {
            if (isHeader) {
              pdf.setFillColor(244, 247, 251);
              pdf.rect(cellX, cursorY, colWidth, rowHeight, 'FD');
            } else {
              pdf.rect(cellX, cursorY, colWidth, rowHeight);
            }

            let textY = cursorY + cellPaddingTop + 4;
            for (const lineParts of cellLines[index]) {
              let textX = cellX + cellPaddingX;
              for (const part of lineParts) {
                pdf.setFont('helvetica', part.style);
                pdf.setFontSize(baseFontSize);
                pdf.text(part.text, textX, textY);
                textX += pdf.getTextWidth(part.text);
              }
              textY += 5;
            }

            cellX += colWidth;
          }

          cursorY += rowHeight;
        };

        drawRow(normalizedHeader, true);
        for (const row of normalizedRows) {
          drawRow(row, false);
        }
        cursorY += 4;
      };

      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(22);
      pdf.text(this.title(), margin, cursorY);
      cursorY += 10;

      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(10);
      pdf.text('Stagione 2025/26 · Regolamento ufficiale', margin, cursorY);
      cursorY += 10;

      for (const section of sections) {
        ensureSpace(14);
        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(16);
        pdf.text(section.title, margin, cursorY);
        cursorY += 8;

        const lines = section.body.split(/\r?\n/);

        for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
          const rawLine = lines[lineIndex];
          const line = rawLine.trim();

          if (!line) {
            cursorY += 3;
            continue;
          }

          if (line.startsWith('### ')) {
            ensureSpace(10);
            pdf.setFont('helvetica', 'bold');
            pdf.setFontSize(13);
            pdf.text(line.slice(4).trim(), margin, cursorY);
            cursorY += 7;
            continue;
          }

          if (line.startsWith('#### ')) {
            ensureSpace(9);
            pdf.setFont('helvetica', 'bold');
            pdf.setFontSize(12);
            pdf.text(line.slice(5).trim(), margin, cursorY);
            cursorY += 6;
            continue;
          }

          if (line.startsWith('|')) {
            const tableBlock: string[] = [line];
            let scanIndex = lineIndex + 1;

            while (scanIndex < lines.length) {
              const candidate = lines[scanIndex].trim();
              if (!candidate.startsWith('|')) {
                break;
              }
              tableBlock.push(candidate);
              scanIndex += 1;
            }

            const dividerIndex = tableBlock.findIndex(
              (row, index) => index > 0 && isMarkdownTableDivider(row),
            );

            if (dividerIndex > 0) {
              const header = parseTableRow(tableBlock[0]);
              const rows = tableBlock
                .slice(dividerIndex + 1)
                .filter((row) => !isMarkdownTableDivider(row))
                .map((row) => parseTableRow(row));
              renderTable(header, rows);
              lineIndex = scanIndex - 1;
              continue;
            }

            if (tableBlock.length > 1) {
              const header = parseTableRow(tableBlock[0]);
              const rows = tableBlock.slice(1).map((row) => parseTableRow(row));
              renderTable(header, rows);
              lineIndex = scanIndex - 1;
              continue;
            }

            addWrappedText(line.replace(/^\|/, '').replace(/\|$/, '').replace(/\|/g, ' · '), 10);
            continue;
          }

          if (/^\d+\.\s+/.test(line)) {
            const match = line.match(/^(\d+)\.\s+(.*)$/);
            if (match) {
              addNumberedItem(Number(match[1]), match[2]);
              continue;
            }
          }

          if (line.startsWith('- ')) {
            addListItem(line.slice(2));
            continue;
          }

          addWrappedText(line, 11);
        }

        cursorY += 4;
      }

      pdf.save('regolamento-ffl-2025-26.pdf');
    } finally {
      this.exporting.set(false);
    }
  }

  private parseMarkdown(markdown: string) {
    const lines = markdown.split(/\r?\n/);
    const sections: RegulationSection[] = [];
    let currentTitle = '';
    let currentBody: string[] = [];

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();

      if (line.startsWith('# ')) {
        this.title.set(line.slice(2).trim());
        continue;
      }

      if (line.startsWith('## ')) {
        if (currentTitle) {
          sections.push({
            id: this.slugify(currentTitle),
            title: currentTitle,
            body: currentBody.join('\n').trim(),
          });
        }

        currentTitle = line.slice(3).trim();
        currentBody = [];
        continue;
      }

      if (currentTitle) {
        currentBody.push(rawLine);
      }
    }

    if (currentTitle) {
      sections.push({
        id: this.slugify(currentTitle),
        title: currentTitle,
        body: currentBody.join('\n').trim(),
      });
    }

    this.sections.set(sections);
  }

  private slugify(value: string) {
    return value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }
}
