"""
ICU Guard v5.0 — Patient Table Component
Provides sortable, filterable, paginated clinical patient registry with
custom tier badges, search, and row-click clinical preview.
"""

from typing import Callable, Dict, Any, List, Optional
from nicegui import ui

from dashboard.config import config
from dashboard.utils.constants import (
    PATIENT_TABLE_COLUMNS,
    TIER_COLORS,
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    TIER_STABLE,
)


class PatientTable:
    """Encapsulates the Quasar/NiceGUI QTable for 1,706 ICU cohort patients."""

    def __init__(
        self,
        records: List[Dict[str, Any]],
        on_select: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_simulate: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.all_records = records
        self.filtered_records = records
        self.on_select = on_select
        self.on_simulate = on_simulate
        self.selected_patient: Optional[Dict[str, Any]] = None

        self._build_table()

    def _build_table(self) -> None:
        """Constructs the NiceGUI table with custom Quasar scoped slots."""
        self.table = ui.table(
            columns=PATIENT_TABLE_COLUMNS,
            rows=self.filtered_records,
            row_key="id",
            pagination={"rowsPerPage": config.ROWS_PER_PAGE, "sortBy": "id", "descending": False},
        ).classes("w-full glass-card")

        # Quasar properties for dark mode, hover, and responsive layout
        self.table.props("dark flat bordered separator=horizontal binary-state-sort dense")

        # Custom Slot: Color-Coded TIER Badge
        self.table.add_slot(
            "body-cell-tier",
            """
            <q-td :props="props">
                <span :style="{
                    backgroundColor: props.value === 'CRITICAL' ? 'rgba(220, 20, 60, 0.18)' :
                                     props.value === 'HIGH' ? 'rgba(255, 140, 0, 0.18)' :
                                     props.value === 'MODERATE' ? 'rgba(255, 215, 0, 0.18)' : 'rgba(50, 205, 50, 0.18)',
                    color: props.value === 'CRITICAL' ? '#ff4d6d' :
                           props.value === 'HIGH' ? '#ffa94d' :
                           props.value === 'MODERATE' ? '#ffe066' : '#69db7c',
                    border: '1px solid ' + (props.value === 'CRITICAL' ? '#DC143C' :
                                            props.value === 'HIGH' ? '#FF8C00' :
                                            props.value === 'MODERATE' ? '#FFD700' : '#32CD32'),
                    padding: '3px 8px',
                    borderRadius: '5px',
                    fontWeight: '700',
                    fontSize: '0.72rem',
                    letterSpacing: '0.04em',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                }">
                    <span :style="{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: props.value === 'CRITICAL' ? '#DC143C' :
                                         props.value === 'HIGH' ? '#FF8C00' :
                                         props.value === 'MODERATE' ? '#FFD700' : '#32CD32'
                    }"></span>
                    {{ props.value }}
                </span>
            </q-td>
            """,
        )

        # Custom Slot: Deterioration Risk Cell
        self.table.add_slot(
            "body-cell-p_deterioration",
            """
            <q-td :props="props">
                <div class="row items-center justify-center q-gutter-xs">
                    <span class="text-caption text-weight-bold" :class="parseFloat(props.value) > 50 ? 'text-negative' : 'text-grey-4'">
                        {{ props.value }}
                    </span>
                </div>
            </q-td>
            """,
        )

        # Custom Slot: Actions (Preview & Select)
        self.table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props">
                <div class="row justify-center q-gutter-xs no-wrap">
                    <q-btn size="sm" dense flat round color="cyan-4" icon="visibility" @click.stop="$parent.$emit('preview', props.row)">
                        <q-tooltip>Quick Clinical Preview</q-tooltip>
                    </q-btn>
                    <q-btn size="sm" dense unelevated color="primary" label="Select" icon="check_circle" @click.stop="$parent.$emit('select', props.row)">
                        <q-tooltip>Select Patient for Simulation</q-tooltip>
                    </q-btn>
                </div>
            </q-td>
            """,
        )

        # Attach Event Listeners
        self.table.on("preview", self._handle_preview)
        self.table.on("select", self._handle_select)
        self.table.on("rowClick", self._handle_row_click)

    def _handle_preview(self, e) -> None:
        row = e.args if isinstance(e.args, dict) else e.args[0] if isinstance(e.args, list) and e.args else None
        if row and self.on_select:
            self.on_select(row)

    def _handle_select(self, e) -> None:
        row = e.args if isinstance(e.args, dict) else e.args[0] if isinstance(e.args, list) and e.args else None
        if row and self.on_simulate:
            self.on_simulate(row)

    def _handle_row_click(self, e) -> None:
        """Handles click anywhere on a row to trigger selection preview."""
        try:
            # Quasar rowClick passes (evt, row, index)
            if isinstance(e.args, list) and len(e.args) > 1 and isinstance(e.args[1], dict):
                row = e.args[1]
            elif isinstance(e.args, dict):
                row = e.args
            else:
                return

            if self.on_select:
                self.on_select(row)
        except Exception:
            pass

    def update_rows(self, rows: List[Dict[str, Any]]) -> None:
        """Updates the table rows reactively upon filter/search changes."""
        self.filtered_records = rows
        self.table.rows = rows
        self.table.update()
