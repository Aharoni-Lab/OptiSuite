// Decompiled from: SC3U, Version=1.6.0.0, Culture=neutral, PublicKeyToken=null
// Assembly Location: C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op_new_052825\SC3U.dll


// Type: SC3Us.MainClass
public class MainClass
{
    // Method: GetPrivateProfileString() -> System.Int64
    // Method: WritePrivateProfileString() -> System.Int64
    // Method: GetFromIni() -> System.String
    // Method: WriteToIni() -> System.Boolean
    // Method: GetControl() -> System.Void
    // Method: Equals() -> System.Boolean
    // Method: GetHashCode() -> System.Int32
    // Method: Finalize() -> System.Void
    // Method: GetType() -> System.Type
    // Method: MemberwiseClone() -> System.Object
    // Method: ToString() -> System.String
}


// Type: SC3Us.SC3U
public class SC3U
{
    // Method: Finalize() -> System.Void
    // Method: ConnectPort() -> System.Void
    // Method: ClosePort() -> System.Void
    // Method: StopDelay() -> System.Void
    // Method: GetActualSpeed() -> System.Double
    // Method: GetPulseEquivalent() -> System.Double
    // Method: GetType() -> System.Int16
    // Method: GetUnit() -> System.Int16
    // Method: GetMotorAngle() -> System.Single
    // Method: GetSubsection() -> System.Int16
    // Method: GetPitch() -> System.Single
    // Method: GetTranRatio() -> System.Int32
    // Method: GetTravel() -> System.Double
    // Method: GetNegativeTravel() -> System.Int64
    // Method: GetPositiveTravel() -> System.Int64
    // Method: GetCurrentStep() -> System.Int64
    // Method: GetCurrentPosition() -> System.Double
    // Method: GetZeroOffset() -> System.Int64
    // Method: SetType() -> System.Int16
    // Method: SetUnit() -> System.Int16
    // Method: SetMotorAngle() -> System.Int16
    // Method: SetSubsection() -> System.Int16
    // Method: SetPitch() -> System.Int16
    // Method: SetTranRatio() -> System.Int16
    // Method: SetTravel() -> System.Int16
    // Method: SetNegativeTravel() -> System.Int16
    // Method: SetPositiveTravel() -> System.Int16
    // Method: SetZeroOffset() -> System.Int16
    // Method: RefreshCurrentPosition() -> System.Int16
    // Method: RunToZero() -> System.Int16
    // Method: RunToStep() -> System.Int16
    // Method: RunToPosition() -> System.Int16
    // Method: StopRun() -> System.Int16
    // Method: SaveParam() -> System.Int16
    // Method: DisplayParameterInterface() -> System.Void
    // Method: DisplayOperationInterface() -> System.Void
    // Method: SetUseMode() -> System.Int16
    // Method: GetUseMode() -> System.Int16
    // Method: GetShutterStatus() -> System.Int16
    // Method: OpenShutter() -> System.Int16
    // Method: CloseShutter() -> System.Int16
    // Method: FreeUp() -> System.Int16
    // Method: FreeDown() -> System.Int16
    // Method: FixIncrease() -> System.Int16
    // Method: FixDecrease() -> System.Int16
    // Method: SendCommand() -> System.Void
    // Method: Delay() -> System.Void
    // Method: DelayWait() -> System.Void
    // Method: SetSpeed() -> System.Int16
    // Method: ReadParam() -> System.Void
    // Method: GetCurrAxis() -> System.Void
    // Method: RefreshParam() -> System.Void
    // Method: StringToLong() -> System.Int64
    // Method: RefreshShow() -> System.Void
    // Method: SendRunToZeroAndShow() -> System.Void
    // Method: AxisName() -> System.String
    // Method: ChangeLanguage() -> System.Void
    // Method: ControlEnable() -> System.Void
    // Method: IsNumber() -> System.Boolean
    // Method: SCPort_DataReceived() -> System.Void
    // Method: BtnParamSet_Click() -> System.Void
    // Method: RadAxis_CheckedChanged() -> System.Void
    // Method: BtnOk_Click() -> System.Void
    // Method: CboType_SelectedIndexChanged() -> System.Void
    // Method: BtnClose_Click() -> System.Void
    // Method: CboSpeed_SelectedIndexChanged() -> System.Void
    // Method: CboTravel_Validating() -> System.Void
    // Method: CboNegaTravel_Validating() -> System.Void
    // Method: CboPosiTravel_Validating() -> System.Void
    // Method: CboPitch_Validating() -> System.Void
    // Method: CboTranRatio_Validating() -> System.Void
    // Method: timer1_Tick() -> System.Void
    // Method: BtnRun_Click() -> System.Void
    // Method: BtnFreeUp_Click() -> System.Void
    // Method: BtnFreeDown_Click() -> System.Void
    // Method: BtnFixAdd_Click() -> System.Void
    // Method: BtnFixSub_Click() -> System.Void
    // Method: BtnLimitReturnZero_Click() -> System.Void
    // Method: BtnStop_Click() -> System.Void
    // Method: BtnSetZero_Click() -> System.Void
    // Method: BtnCancelZero_Click() -> System.Void
    // Method: SCU_Load() -> System.Void
    // Method: RefreshShutterDisplay() -> System.Int16
    // Method: Dispose() -> System.Void
    // Method: InitializeComponent() -> System.Void
    // Method: OnLoad() -> System.Void
    // Method: OnResize() -> System.Void
    // Method: WndProc() -> System.Void
    // Method: ValidateChildren() -> System.Boolean
    // Method: ValidateChildren() -> System.Boolean
    // Method: OnCreateControl() -> System.Void
    // Method: OnMouseDown() -> System.Void
    // Method: System.Windows.Forms.IContainerControl.ActivateControl() -> System.Boolean
    // Method: AdjustFormScrollbars() -> System.Void
    // Method: CanProcessMnemonic() -> System.Boolean
    // Method: GetToolNativeScreenRectangle() -> System.Drawing.Rectangle
    // Method: OnAutoScaleModeChanged() -> System.Void
    // Method: OnAutoValidateChanged() -> System.Void
    // Method: OnFrameWindowActivate() -> System.Void
    // Method: OnLayout() -> System.Void
    // Method: OnLayoutResuming() -> System.Void
    // Method: OnParentChanged() -> System.Void
    // Method: ProcessDialogChar() -> System.Boolean
    // Method: ProcessDialogKey() -> System.Boolean
    // Method: ProcessCmdKey() -> System.Boolean
    // Method: ProcessMnemonic() -> System.Boolean
    // Method: ProcessTabKey() -> System.Boolean
    // Method: Select() -> System.Void
    // Method: UpdateDefaultButton() -> System.Void
    // Method: ShouldSerializeAutoValidate() -> System.Boolean
    // Method: ActivateControlInternal() -> System.Boolean
    // Method: ActivateControlInternal() -> System.Boolean
    // Method: HasFocusableChild() -> System.Boolean
    // Method: AfterControlRemoved() -> System.Void
    // Method: CreateAxContainer() -> System.Windows.Forms.AxHost+AxContainer
    // Method: FocusActiveControlInternal() -> System.Void
    // Method: GetPreferredSizeCore() -> System.Drawing.Size
    // Method: OnChildLayoutResuming() -> System.Void
    // Method: OnFontChanged() -> System.Void
    // Method: FormDpiChanged() -> System.Void
    // Method: PerformAutoScale() -> System.Void
    // Method: ResumeAllLayout() -> System.Void
    // Method: SuspendAllLayout() -> System.Void
    // Method: Scale() -> System.Void
    // Method: SetActiveControlInternal() -> System.Void
    // Method: UpdateFocusedControl() -> System.Void
    // Method: Validate() -> System.Boolean
    // Method: Validate() -> System.Boolean
    // Method: ValidateInternal() -> System.Boolean
    // Method: ResetActiveAndFocusedControlsRecursive() -> System.Void
    // Method: OnMouseWheel() -> System.Void
    // Method: OnRightToLeftChanged() -> System.Void
    // Method: OnPaintBackground() -> System.Void
    // Method: OnPaddingChanged() -> System.Void
    // Method: OnVisibleChanged() -> System.Void
    // Method: ScaleCore() -> System.Void
    // Method: ScaleControl() -> System.Void
    // Method: ScrollToControl() -> System.Drawing.Point
    // Method: OnScroll() -> System.Void
    // Method: GetScrollState() -> System.Boolean
    // Method: ScaleDockPadding() -> System.Void
    // Method: SetDisplayFromScrollProps() -> System.Void
    // Method: SetDisplayRectLocation() -> System.Void
    // Method: ScrollControlIntoView() -> System.Void
    // Method: SetAutoScrollMargin() -> System.Void
    // Method: SetScrollState() -> System.Void
    // Method: GetAccessibilityObjectById() -> System.Windows.Forms.AccessibleObject
    // Method: NotifyValidationResult() -> System.Void
    // Method: GetPreferredSize() -> System.Drawing.Size
    // Method: AddReflectChild() -> System.Void
    // Method: RemoveReflectChild() -> System.Void
    // Method: AssignParent() -> System.Void
    // Method: BeginInvoke() -> System.IAsyncResult
    // Method: CanSelectCore() -> System.Boolean
    // Method: CreateControlsInstance() -> System.Windows.Forms.Control+ControlCollection
    // Method: CreateHandle() -> System.Void
    // Method: DefWndProc() -> System.Void
    // Method: DestroyHandle() -> System.Void
    // Method: DisposeAxControls() -> System.Void
    // Method: EndInvoke() -> System.Object
    // Method: FocusInternal() -> System.Boolean
    // Method: GetScaledBounds() -> System.Drawing.Rectangle
    // Method: GetVisibleCore() -> System.Boolean
    // Method: GetFirstChildControlInTabOrder() -> System.Windows.Forms.Control
    // Method: InitLayout() -> System.Void
    // Method: InitializeDCForWmCtlColor() -> System.IntPtr
    // Method: Invoke() -> System.Object
    // Method: IsInputChar() -> System.Boolean
    // Method: IsInputKey() -> System.Boolean
    // Method: NotifyInvalidate() -> System.Void
    // Method: OnAutoSizeChanged() -> System.Void
    // Method: OnBackColorChanged() -> System.Void
    // Method: OnBackgroundImageChanged() -> System.Void
    // Method: OnBackgroundImageLayoutChanged() -> System.Void
    // Method: OnBindingContextChanged() -> System.Void
    // Method: OnCausesValidationChanged() -> System.Void
    // Method: OnContextMenuChanged() -> System.Void
    // Method: OnContextMenuStripChanged() -> System.Void
    // Method: OnCursorChanged() -> System.Void
    // Method: OnDockChanged() -> System.Void
    // Method: OnEnabledChanged() -> System.Void
    // Method: OnForeColorChanged() -> System.Void
    // Method: OnNotifyMessage() -> System.Void
    // Method: OnParentBackColorChanged() -> System.Void
    // Method: OnParentBackgroundImageChanged() -> System.Void
    // Method: OnParentBindingContextChanged() -> System.Void
    // Method: OnParentCursorChanged() -> System.Void
    // Method: OnParentEnabledChanged() -> System.Void
    // Method: OnParentFontChanged() -> System.Void
    // Method: OnParentHandleRecreated() -> System.Void
    // Method: OnParentHandleRecreating() -> System.Void
    // Method: OnParentForeColorChanged() -> System.Void
    // Method: OnParentRightToLeftChanged() -> System.Void
    // Method: OnParentVisibleChanged() -> System.Void
    // Method: OnParentBecameInvisible() -> System.Void
    // Method: OnPrint() -> System.Void
    // Method: OnTabIndexChanged() -> System.Void
    // Method: OnTabStopChanged() -> System.Void
    // Method: OnTextChanged() -> System.Void
    // Method: OnTopMostActiveXParentChanged() -> System.Void
    // Method: OnClick() -> System.Void
    // Method: OnClientSizeChanged() -> System.Void
    // Method: OnControlAdded() -> System.Void
    // Method: OnControlRemoved() -> System.Void
    // Method: OnInvokedSetScrollPosition() -> System.Void
    // Method: OnLocationChanged() -> System.Void
    // Method: OnHandleDestroyed() -> System.Void
    // Method: OnDoubleClick() -> System.Void
    // Method: OnDragEnter() -> System.Void
    // Method: OnDragOver() -> System.Void
    // Method: OnDragLeave() -> System.Void
    // Method: OnDragDrop() -> System.Void
    // Method: OnGiveFeedback() -> System.Void
    // Method: OnEnter() -> System.Void
    // Method: OnGotFocus() -> System.Void
    // Method: OnHelpRequested() -> System.Void
    // Method: OnInvalidated() -> System.Void
    // Method: OnKeyDown() -> System.Void
    // Method: OnKeyPress() -> System.Void
    // Method: OnKeyUp() -> System.Void
    // Method: OnLayoutSuspended() -> System.Void
    // Method: OnLeave() -> System.Void
    // Method: OnLostFocus() -> System.Void
    // Method: OnMarginChanged() -> System.Void
    // Method: OnMouseDoubleClick() -> System.Void
    // Method: OnMouseClick() -> System.Void
    // Method: OnMouseCaptureChanged() -> System.Void
    // Method: OnMouseEnter() -> System.Void
    // Method: OnMouseLeave() -> System.Void
    // Method: OnDpiChangedBeforeParent() -> System.Void
    // Method: OnDpiChangedAfterParent() -> System.Void
    // Method: OnMouseHover() -> System.Void
    // Method: OnMouseMove() -> System.Void
    // Method: OnMouseUp() -> System.Void
    // Method: OnMove() -> System.Void
    // Method: OnPaint() -> System.Void
    // Method: OnQueryContinueDrag() -> System.Void
    // Method: OnRegionChanged() -> System.Void
    // Method: OnPreviewKeyDown() -> System.Void
    // Method: OnSizeChanged() -> System.Void
    // Method: OnChangeUICues() -> System.Void
    // Method: OnStyleChanged() -> System.Void
    // Method: OnSystemColorsChanged() -> System.Void
    // Method: OnValidating() -> System.Void
    // Method: OnValidated() -> System.Void
    // Method: RescaleConstantsForDpi() -> System.Void
    // Method: PreProcessMessage() -> System.Boolean
    // Method: ProcessKeyMessage() -> System.Boolean
    // Method: ProcessKeyPreview() -> System.Boolean
    // Method: ResetCursor() -> System.Void
    // Method: ResetFont() -> System.Void
    // Method: ResetRightToLeft() -> System.Void
    // Method: Refresh() -> System.Void
    // Method: ResetText() -> System.Void
    // Method: SetBoundsCore() -> System.Void
    // Method: SetClientSizeCore() -> System.Void
    // Method: SizeFromClientSize() -> System.Drawing.Size
    // Method: SetVisibleCore() -> System.Void
    // Method: ShouldPerformContainerValidation() -> System.Boolean
    // Method: ShouldSerializeBackColor() -> System.Boolean
    // Method: ShouldSerializeCursor() -> System.Boolean
    // Method: ShouldSerializeForeColor() -> System.Boolean
    // Method: ShouldSerializeFont() -> System.Boolean
    // Method: ShouldSerializeRightToLeft() -> System.Boolean
    // Method: ShouldSerializeMaximumSize() -> System.Boolean
    // Method: ShouldSerializeMinimumSize() -> System.Boolean
    // Method: ShouldSerializeSize() -> System.Boolean
    // Method: ShouldSerializeText() -> System.Boolean
    // Method: UpdateStylesCore() -> System.Void
    // Method: OnBoundsUpdate() -> System.Void
    // Method: WmContextMenu() -> System.Void
    // Method: System.Windows.Forms.Layout.IArrangedElement.PerformLayout() -> System.Void
    // Method: System.Windows.Forms.Layout.IArrangedElement.SetBounds() -> System.Void
    // Method: System.Windows.Forms.IDropTarget.OnDragEnter() -> System.Void
    // Method: System.Windows.Forms.IDropTarget.OnDragOver() -> System.Void
    // Method: System.Windows.Forms.IDropTarget.OnDragLeave() -> System.Void
    // Method: System.Windows.Forms.IDropTarget.OnDragDrop() -> System.Void
    // Method: System.Windows.Forms.ISupportOleDropSource.OnGiveFeedback() -> System.Void
    // Method: System.Windows.Forms.ISupportOleDropSource.OnQueryContinueDrag() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleControl.GetControlInfo() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleControl.OnMnemonic() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleControl.OnAmbientPropertyChange() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleControl.FreezeEvents() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.GetWindow() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.ContextSensitiveHelp() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.TranslateAccelerator() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.OnFrameWindowActivate() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.OnDocWindowActivate() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.ResizeBorder() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceActiveObject.EnableModeless() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceObject.GetWindow() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceObject.ContextSensitiveHelp() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceObject.InPlaceDeactivate() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceObject.UIDeactivate() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceObject.SetObjectRects() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleInPlaceObject.ReactivateAndUndo() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.SetClientSite() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetClientSite() -> System.Windows.Forms.UnsafeNativeMethods+IOleClientSite
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.SetHostNames() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.Close() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.SetMoniker() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetMoniker() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.InitFromData() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetClipboardData() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.DoVerb() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.EnumVerbs() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.OleUpdate() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.IsUpToDate() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetUserClassID() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetUserType() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.SetExtent() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetExtent() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.Advise() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.Unadvise() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.EnumAdvise() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.GetMiscStatus() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleObject.SetColorScheme() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleWindow.GetWindow() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IOleWindow.ContextSensitiveHelp() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersist.GetClassID() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistPropertyBag.InitNew() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistPropertyBag.GetClassID() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistPropertyBag.Load() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistPropertyBag.Save() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.GetClassID() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.IsDirty() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.InitNew() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.Load() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.Save() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.SaveCompleted() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStorage.HandsOffStorage() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStreamInit.GetClassID() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStreamInit.IsDirty() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStreamInit.Load() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStreamInit.Save() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStreamInit.GetSizeMax() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IPersistStreamInit.InitNew() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IQuickActivate.QuickActivate() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IQuickActivate.SetContentExtent() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IQuickActivate.GetContentExtent() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject.Draw() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject.GetColorSet() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject.Freeze() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject.Unfreeze() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject.SetAdvise() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject.GetAdvise() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.Draw() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.GetColorSet() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.Freeze() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.Unfreeze() -> System.Int32
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.SetAdvise() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.GetAdvise() -> System.Void
    // Method: System.Windows.Forms.UnsafeNativeMethods.IViewObject2.GetExtent() -> System.Void
    // Method: System.Windows.Forms.IKeyboardToolTip.CanShowToolTipsNow() -> System.Boolean
    // Method: System.Windows.Forms.IKeyboardToolTip.GetNativeScreenRectangle() -> System.Drawing.Rectangle
    // Method: System.Windows.Forms.IKeyboardToolTip.GetNeighboringToolsRectangles() -> System.Collections.Generic.IList`1[System.Drawing.Rectangle]
    // Method: System.Windows.Forms.IKeyboardToolTip.IsHoveredWithMouse() -> System.Boolean
    // Method: System.Windows.Forms.IKeyboardToolTip.HasRtlModeEnabled() -> System.Boolean
    // Method: System.Windows.Forms.IKeyboardToolTip.AllowsToolTip() -> System.Boolean
    // Method: System.Windows.Forms.IKeyboardToolTip.GetOwnerWindow() -> System.Windows.Forms.IWin32Window
    // Method: System.Windows.Forms.IKeyboardToolTip.OnHooked() -> System.Void
    // Method: System.Windows.Forms.IKeyboardToolTip.OnUnhooked() -> System.Void
    // Method: System.Windows.Forms.IKeyboardToolTip.GetCaptionForTool() -> System.String
    // Method: System.Windows.Forms.IKeyboardToolTip.ShowsOwnToolTip() -> System.Boolean
    // Method: System.Windows.Forms.IKeyboardToolTip.IsBeingTabbedTo() -> System.Boolean
    // Method: System.Windows.Forms.IKeyboardToolTip.AllowsChildrenToShowToolTips() -> System.Boolean
    // Method: ShowsOwnKeyboardToolTip() -> System.Boolean
    // Method: OnKeyboardToolTipHook() -> System.Void
    // Method: OnKeyboardToolTipUnhook() -> System.Void
    // Method: AllowsKeyboardToolTip() -> System.Boolean
    // Method: AllowsChildrenToShowToolTips() -> System.Boolean
    // Method: OnImeModeChanged() -> System.Void
    // Method: ShouldSerializeImeMode() -> System.Boolean
    // Method: SetAutoSizeMode() -> System.Void
    // Method: GetAutoSizeMode() -> System.Windows.Forms.AutoSizeMode
    // Method: ResetBindings() -> System.Void
    // Method: ValidateActiveControl() -> System.Boolean
    // Method: ScaleFont() -> System.Void
    // Method: AccessibilityNotifyClients() -> System.Void
    // Method: AccessibilityNotifyClients() -> System.Void
    // Method: BeginInvoke() -> System.IAsyncResult
    // Method: BeginUpdateInternal() -> System.Void
    // Method: BringToFront() -> System.Void
    // Method: Contains() -> System.Boolean
    // Method: CreateAccessibilityInstance() -> System.Windows.Forms.AccessibleObject
    // Method: CreateGraphics() -> System.Drawing.Graphics
    // Method: CreateGraphicsInternal() -> System.Drawing.Graphics
    // Method: CreateControl() -> System.Void
    // Method: CreateControl() -> System.Void
    // Method: DoDragDrop() -> System.Windows.Forms.DragDropEffects
    // Method: DrawToBitmap() -> System.Void
    // Method: EndUpdateInternal() -> System.Boolean
    // Method: EndUpdateInternal() -> System.Boolean
    // Method: FindForm() -> System.Windows.Forms.Form
    // Method: FindFormInternal() -> System.Windows.Forms.Form
    // Method: GetTopLevel() -> System.Boolean
    // Method: RaiseCreateHandleEvent() -> System.Void
    // Method: RaiseKeyEvent() -> System.Void
    // Method: RaiseMouseEvent() -> System.Void
    // Method: Focus() -> System.Boolean
    // Method: ApplySizeConstraints() -> System.Drawing.Size
    // Method: ApplySizeConstraints() -> System.Drawing.Size
    // Method: ApplyBoundsConstraints() -> System.Drawing.Rectangle
    // Method: GetChildAtPoint() -> System.Windows.Forms.Control
    // Method: GetChildAtPoint() -> System.Windows.Forms.Control
    // Method: GetContainerControl() -> System.Windows.Forms.IContainerControl
    // Method: IsUpdating() -> System.Boolean
    // Method: GetContainerControlInternal() -> System.Windows.Forms.IContainerControl
    // Method: GetHRgn() -> System.IntPtr
    // Method: GetAnyDisposingInHierarchy() -> System.Boolean
    // Method: GetChildControlsInTabOrder() -> System.Windows.Forms.Control[]
    // Method: GetNextControl() -> System.Windows.Forms.Control
    // Method: GetState() -> System.Boolean
    // Method: GetStyle() -> System.Boolean
    // Method: Hide() -> System.Void
    // Method: Invalidate() -> System.Void
    // Method: Invalidate() -> System.Void
    // Method: Invalidate() -> System.Void
    // Method: Invalidate() -> System.Void
    // Method: Invalidate() -> System.Void
    // Method: Invalidate() -> System.Void
    // Method: Invoke() -> System.Object
    // Method: InvokePaint() -> System.Void
    // Method: InvokePaintBackground() -> System.Void
    // Method: IsFontSet() -> System.Boolean
    // Method: IsDescendant() -> System.Boolean
    // Method: LogicalToDeviceUnits() -> System.Int32
    // Method: LogicalToDeviceUnits() -> System.Drawing.Size
    // Method: ScaleBitmapLogicalToDevice() -> System.Void
    // Method: AdjustWindowRectEx() -> System.Void
    // Method: NotifyEnter() -> System.Void
    // Method: NotifyLeave() -> System.Void
    // Method: InvokeOnClick() -> System.Void
    // Method: OnHandleCreated() -> System.Void
    // Method: InvokeGotFocus() -> System.Void
    // Method: InvokeLostFocus() -> System.Void
    // Method: PaintBackground() -> System.Void
    // Method: PaintBackground() -> System.Void
    // Method: PaintBackground() -> System.Void
    // Method: PaintTransparentBackground() -> System.Void
    // Method: PaintTransparentBackground() -> System.Void
    // Method: PerformLayout() -> System.Void
    // Method: PerformLayout() -> System.Void
    // Method: PerformLayout() -> System.Void
    // Method: PerformControlValidation() -> System.Boolean
    // Method: PerformContainerValidation() -> System.Boolean
    // Method: PointToClient() -> System.Drawing.Point
    // Method: PointToClientInternal() -> System.Drawing.Point
    // Method: PointToScreen() -> System.Drawing.Point
    // Method: PreProcessControlMessage() -> System.Windows.Forms.PreProcessControlState
    // Method: PrintToMetaFileRecursive() -> System.Void
    // Method: ProcessKeyEventArgs() -> System.Boolean
    // Method: ProcessUICues() -> System.Void
    // Method: RaiseDragEvent() -> System.Void
    // Method: RaisePaintEvent() -> System.Void
    // Method: ResetBackColor() -> System.Void
    // Method: ResetForeColor() -> System.Void
    // Method: RecreateHandle() -> System.Void
    // Method: RecreateHandleCore() -> System.Void
    // Method: RectangleToClient() -> System.Drawing.Rectangle
    // Method: RectangleToScreen() -> System.Drawing.Rectangle
    // Method: ReleaseUiaProvider() -> System.Void
    // Method: ResetMouseEventArgs() -> System.Void
    // Method: ResumeLayout() -> System.Void
    // Method: ResumeLayout() -> System.Void
    // Method: SetAcceptDrops() -> System.Void
    // Method: Scale() -> System.Void
    // Method: Scale() -> System.Void
    // Method: Scale() -> System.Void
    // Method: ScaleChildControls() -> System.Void
    // Method: UpdateWindowFontIfNeeded() -> System.Void
    // Method: ScaleControl() -> System.Void
    // Method: ScaleSize() -> System.Drawing.Size
    // Method: Select() -> System.Void
    // Method: SelectNextControl() -> System.Boolean
    // Method: SelectNextControlInternal() -> System.Boolean
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendMessage() -> System.IntPtr
    // Method: SendToBack() -> System.Void
    // Method: SetBounds() -> System.Void
    // Method: SetBounds() -> System.Void
    // Method: SizeFromClientSize() -> System.Drawing.Size
    // Method: SetState() -> System.Void
    // Method: SetState2() -> System.Void
    // Method: SetStyle() -> System.Void
    // Method: SetTopLevel() -> System.Void
    // Method: SetTopLevelInternal() -> System.Void
    // Method: RtlTranslateAlignment() -> System.Windows.Forms.HorizontalAlignment
    // Method: RtlTranslateAlignment() -> System.Windows.Forms.LeftRightAlignment
    // Method: RtlTranslateAlignment() -> System.Drawing.ContentAlignment
    // Method: RtlTranslateHorizontal() -> System.Windows.Forms.HorizontalAlignment
    // Method: RtlTranslateLeftRight() -> System.Windows.Forms.LeftRightAlignment
    // Method: RtlTranslateContent() -> System.Drawing.ContentAlignment
    // Method: Show() -> System.Void
    // Method: ShouldSerializeMargin() -> System.Boolean
    // Method: ShouldSerializePadding() -> System.Boolean
    // Method: SuspendLayout() -> System.Void
    // Method: Update() -> System.Void
    // Method: UpdateBounds() -> System.Void
    // Method: UpdateBounds() -> System.Void
    // Method: UpdateBounds() -> System.Void
    // Method: UpdateZOrder() -> System.Void
    // Method: UpdateStyles() -> System.Void
    // Method: WindowAssignHandle() -> System.Void
    // Method: WindowReleaseHandle() -> System.Void
    // Method: WmContextMenu() -> System.Void
    // Method: UpdateImeContextMode() -> System.Void
    // Method: VerifyImeRestrictedModeChanged() -> System.Void
    // Method: OnImeContextStatusChanged() -> System.Void
    // Method: ResetImeMode() -> System.Void
    // Method: WmImeSetFocus() -> System.Void
    // Method: Dispose() -> System.Void
    // Method: GetService() -> System.Object
    // Method: ToString() -> System.String
    // Method: GetLifetimeService() -> System.Object
    // Method: InitializeLifetimeService() -> System.Object
    // Method: CreateObjRef() -> System.Runtime.Remoting.ObjRef
    // Method: GetComIUnknown() -> System.IntPtr
    // Method: IsInstanceOfType() -> System.Boolean
    // Method: InvokeMember() -> System.Object
    // Method: MemberwiseClone() -> System.MarshalByRefObject
    // Method: __RaceSetServerIdentity() -> System.Runtime.Remoting.ServerIdentity
    // Method: __ResetServerIdentity() -> System.Void
    // Method: CanCastToXmlType() -> System.Boolean
    // Method: Equals() -> System.Boolean
    // Method: GetHashCode() -> System.Int32
    // Method: GetType() -> System.Type
    // Method: MemberwiseClone() -> System.Object
    // Property: Port: System.Int16
    // Property: ConnectStatus: System.Boolean
    // Property: BusyStatus: System.Boolean
    // Property: ParameterFlag: System.Boolean
    // Property: Language: System.Int16
    // Property: SpeedGrades: System.Int16
    // Property: ShutterSpeedGrades: System.Int16
    // Property: CurrentAxis: System.Int16
    // Property: AutoSize: System.Boolean
    // Property: AutoSizeMode: System.Windows.Forms.AutoSizeMode
    // Property: AutoValidate: System.Windows.Forms.AutoValidate
    // Property: BorderStyle: System.Windows.Forms.BorderStyle
    // Property: CreateParams: System.Windows.Forms.CreateParams
    // Property: DefaultSize: System.Drawing.Size
    // Property: Text: System.String
    // Property: AutoScaleDimensions: System.Drawing.SizeF
    // Property: AutoScaleFactor: System.Drawing.SizeF
    // Property: AutoScaleMode: System.Windows.Forms.AutoScaleMode
    // Property: BindingContext: System.Windows.Forms.BindingContext
    // Property: CanEnableIme: System.Boolean
    // Property: ActiveControl: System.Windows.Forms.Control
    // Property: CurrentAutoScaleDimensions: System.Drawing.SizeF
    // Property: ParentForm: System.Windows.Forms.Form
    // Property: ParentFormInternal: System.Windows.Forms.Form
    // Property: InnerMostActiveContainerControl: System.Windows.Forms.ContainerControl
    // Property: InnerMostFocusedContainerControl: System.Windows.Forms.ContainerControl
    // Property: AutoScroll: System.Boolean
    // Property: AutoScrollMargin: System.Drawing.Size
    // Property: AutoScrollPosition: System.Drawing.Point
    // Property: AutoScrollMinSize: System.Drawing.Size
    // Property: DisplayRectangle: System.Drawing.Rectangle
    // Property: HScroll: System.Boolean
    // Property: HorizontalScroll: System.Windows.Forms.HScrollProperties
    // Property: VScroll: System.Boolean
    // Property: VerticalScroll: System.Windows.Forms.VScrollProperties
    // Property: DockPadding: System.Windows.Forms.ScrollableControl+DockPaddingEdges
    // Property: DpiAwarenessContext: System.Windows.Forms.DpiAwarenessContext
    // Property: AccessibilityObject: System.Windows.Forms.AccessibleObject
    // Property: AccessibleDefaultActionDescription: System.String
    // Property: AccessibleDescription: System.String
    // Property: AccessibleName: System.String
    // Property: AccessibleRole: System.Windows.Forms.AccessibleRole
    // Property: AllowDrop: System.Boolean
    // Property: Anchor: System.Windows.Forms.AnchorStyles
    // Property: AutoScrollOffset: System.Drawing.Point
    // Property: LayoutEngine: System.Windows.Forms.Layout.LayoutEngine
    // Property: BackColorBrush: System.IntPtr
    // Property: BackColor: System.Drawing.Color
    // Property: BackgroundImage: System.Drawing.Image
    // Property: BackgroundImageLayout: System.Windows.Forms.ImageLayout
    // Property: BecomingActiveControl: System.Boolean
    // Property: BindingContextInternal: System.Windows.Forms.BindingContext
    // Property: Bottom: System.Int32
    // Property: Bounds: System.Drawing.Rectangle
    // Property: CanAccessProperties: System.Boolean
    // Property: CanFocus: System.Boolean
    // Property: CanRaiseEvents: System.Boolean
    // Property: CanSelect: System.Boolean
    // Property: Capture: System.Boolean
    // Property: CaptureInternal: System.Boolean
    // Property: CausesValidation: System.Boolean
    // Property: CacheTextInternal: System.Boolean
    // Property: ClientRectangle: System.Drawing.Rectangle
    // Property: ClientSize: System.Drawing.Size
    // Property: CompanyName: System.String
    // Property: ContainsFocus: System.Boolean
    // Property: ContextMenu: System.Windows.Forms.ContextMenu
    // Property: ContextMenuStrip: System.Windows.Forms.ContextMenuStrip
    // Property: Controls: System.Windows.Forms.Control+ControlCollection
    // Property: Created: System.Boolean
    // Property: ValidationCancelled: System.Boolean
    // Property: IsTopMdiWindowClosing: System.Boolean
    // Property: IsCurrentlyBeingScaled: System.Boolean
    // Property: CreateThreadId: System.Int32
    // Property: Cursor: System.Windows.Forms.Cursor
    // Property: DataBindings: System.Windows.Forms.ControlBindingsCollection
    // Property: DefaultCursor: System.Windows.Forms.Cursor
    // Property: DefaultMargin: System.Windows.Forms.Padding
    // Property: DefaultMaximumSize: System.Drawing.Size
    // Property: DefaultMinimumSize: System.Drawing.Size
    // Property: DefaultPadding: System.Windows.Forms.Padding
    // Property: DeviceDpi: System.Int32
    // Property: DisabledColor: System.Drawing.Color
    // Property: IsDisposed: System.Boolean
    // Property: Disposing: System.Boolean
    // Property: Dock: System.Windows.Forms.DockStyle
    // Property: DoubleBuffered: System.Boolean
    // Property: Enabled: System.Boolean
    // Property: Focused: System.Boolean
    // Property: Font: System.Drawing.Font
    // Property: FontHandle: System.IntPtr
    // Property: FontHeight: System.Int32
    // Property: ForeColor: System.Drawing.Color
    // Property: Handle: System.IntPtr
    // Property: HandleInternal: System.IntPtr
    // Property: HasChildren: System.Boolean
    // Property: HasMenu: System.Boolean
    // Property: Height: System.Int32
    // Property: HostedInWin32DialogManager: System.Boolean
    // Property: IsHandleCreated: System.Boolean
    // Property: IsLayoutSuspended: System.Boolean
    // Property: IsWindowObscured: System.Boolean
    // Property: InternalHandle: System.IntPtr
    // Property: InvokeRequired: System.Boolean
    // Property: IsAccessible: System.Boolean
    // Property: IsAccessibilityObjectCreated: System.Boolean
    // Property: IsInternalAccessibilityObjectCreated: System.Boolean
    // Property: IsActiveX: System.Boolean
    // Property: IsContainerControl: System.Boolean
    // Property: IsIEParent: System.Boolean
    // Property: IsMirrored: System.Boolean
    // Property: IsMnemonicsListenerAxSourced: System.Boolean
    // Property: Left: System.Int32
    // Property: Location: System.Drawing.Point
    // Property: Margin: System.Windows.Forms.Padding
    // Property: MaximumSize: System.Drawing.Size
    // Property: MinimumSize: System.Drawing.Size
    // Property: Name: System.String
    // Property: Parent: System.Windows.Forms.Control
    // Property: ParentInternal: System.Windows.Forms.Control
    // Property: ProductName: System.String
    // Property: ProductVersion: System.String
    // Property: Properties: System.Windows.Forms.PropertyStore
    // Property: RawBackColor: System.Drawing.Color
    // Property: RecreatingHandle: System.Boolean
    // Property: Region: System.Drawing.Region
    // Property: RenderRightToLeft: System.Boolean
    // Property: RenderTransparent: System.Boolean
    // Property: RenderTransparencyWithVisualStyles: System.Boolean
    // Property: RequiredScaling: System.Windows.Forms.BoundsSpecified
    // Property: RequiredScalingEnabled: System.Boolean
    // Property: ResizeRedraw: System.Boolean
    // Property: Right: System.Int32
    // Property: RightToLeft: System.Windows.Forms.RightToLeft
    // Property: ScaleChildren: System.Boolean
    // Property: Site: System.ComponentModel.ISite
    // Property: Size: System.Drawing.Size
    // Property: TabIndex: System.Int32
    // Property: TabStop: System.Boolean
    // Property: TabStopInternal: System.Boolean
    // Property: Tag: System.Object
    // Property: Top: System.Int32
    // Property: TopLevelControl: System.Windows.Forms.Control
    // Property: TopLevelControlInternal: System.Windows.Forms.Control
    // Property: TopMostParent: System.Windows.Forms.Control
    // Property: ShowKeyboardCues: System.Boolean
    // Property: ShowFocusCues: System.Boolean
    // Property: ShowParams: System.Int32
    // Property: UseWaitCursor: System.Boolean
    // Property: UseCompatibleTextRenderingInt: System.Boolean
    // Property: SupportsUseCompatibleTextRendering: System.Boolean
    // Property: Visible: System.Boolean
    // Property: Width: System.Int32
    // Property: WindowStyle: System.Int32
    // Property: WindowTarget: System.Windows.Forms.IWindowTarget
    // Property: WindowText: System.String
    // Property: PreferredSize: System.Drawing.Size
    // Property: Padding: System.Windows.Forms.Padding
    // Property: ParentContainerControl: System.Windows.Forms.ContainerControl
    // Property: ShouldAutoValidate: System.Boolean
    // Property: SupportsUiaProviders: System.Boolean
    // Property: ToolStripControlHost: System.Windows.Forms.ToolStripControlHost
    // Property: CachedImeMode: System.Windows.Forms.ImeMode
    // Property: CurrentImeContextMode: System.Windows.Forms.ImeMode
    // Property: DefaultImeMode: System.Windows.Forms.ImeMode
    // Property: DisableImeModeChangedCount: System.Int32
    // Property: ImeMode: System.Windows.Forms.ImeMode
    // Property: ImeModeBase: System.Windows.Forms.ImeMode
    // Property: ImeWmCharsToIgnore: System.Int32
    // Property: CanRaiseEventsInternal: System.Boolean
    // Property: Events: System.ComponentModel.EventHandlerList
    // Property: Container: System.ComponentModel.IContainer
    // Property: DesignMode: System.Boolean
    // Field: mMainClass: SC3Us.MainClass
    // Field: BlnConnect: System.Boolean
    // Field: StrReceiver: System.String
    // Field: BlnBusy: System.Boolean
    // Field: BlnReadCom: System.Boolean
    // Field: BlnStopCommand: System.Boolean
    // Field: ShrPort: System.Int16
    // Field: ShrSpeed: System.Int16
    // Field: DblSpeed: System.Double[]
    // Field: ShrType: System.Int16[]
    // Field: ShrUnit: System.Int16[]
    // Field: FlaMotorAngle: System.Single[]
    // Field: ShrSubsection: System.Int16[]
    // Field: FlaPitch: System.Single[]
    // Field: IntTranRatio: System.Int32[]
    // Field: DblTravel: System.Double[]
    // Field: LngNegaTravel: System.Int64[]
    // Field: LngPosiTravel: System.Int64[]
    // Field: ShrCurrAxis: System.Int16
    // Field: LngCurrStep: System.Int64[]
    // Field: DblCurrPosi: System.Double[]
    // Field: DblPulseEqui: System.Double[]
    // Field: LngZeroOffset: System.Int64[]
    // Field: StrAxisName: System.String[]
    // Field: BlnSet: System.Boolean
    // Field: ShrLanguage: System.Int16
    // Field: BlnParamFlag: System.Boolean
    // Field: BlnDonotTip: System.Boolean
    // Field: ShrUseMode: System.Int16[]
    // Field: ShrShutterStatus: System.Int16[]
    // Field: ShrShutterSpeed: System.Int16
    // Field: RadAxis: System.Windows.Forms.RadioButton[]
    // Field: components: System.ComponentModel.IContainer
    // Field: BtnFreeUp: System.Windows.Forms.Button
    // Field: groupBox2: System.Windows.Forms.GroupBox
    // Field: RadXAxis: System.Windows.Forms.RadioButton
    // Field: RadT2Axis: System.Windows.Forms.RadioButton
    // Field: RadT1Axis: System.Windows.Forms.RadioButton
    // Field: RadRAxis: System.Windows.Forms.RadioButton
    // Field: RadZAxis: System.Windows.Forms.RadioButton
    // Field: RadYAxis: System.Windows.Forms.RadioButton
    // Field: BtnRun: System.Windows.Forms.Button
    // Field: BtnLimitReturnZero: System.Windows.Forms.Button
    // Field: label7: System.Windows.Forms.Label
    // Field: BtnFreeDown: System.Windows.Forms.Button
    // Field: NudRunToValue: System.Windows.Forms.NumericUpDown
    // Field: BtnFixSub: System.Windows.Forms.Button
    // Field: BtnStop: System.Windows.Forms.Button
    // Field: BtnFixAdd: System.Windows.Forms.Button
    // Field: LblRunToValueUnit: System.Windows.Forms.Label
    // Field: LblFixValueUnit: System.Windows.Forms.Label
    // Field: BtnSetZero: System.Windows.Forms.Button
    // Field: NudAddOrSubValue: System.Windows.Forms.NumericUpDown
    // Field: label1: System.Windows.Forms.Label
    // Field: LblCurrValue: System.Windows.Forms.Label
    // Field: LblCurrUnit: System.Windows.Forms.Label
    // Field: BtnCancelZero: System.Windows.Forms.Button
    // Field: label4: System.Windows.Forms.Label
    // Field: LblCurrSpeed: System.Windows.Forms.Label
    // Field: BtnParamSet: System.Windows.Forms.Button
    // Field: CboType: System.Windows.Forms.ComboBox
    // Field: label6: System.Windows.Forms.Label
    // Field: CboUnit: System.Windows.Forms.ComboBox
    // Field: label8: System.Windows.Forms.Label
    // Field: CboMotorAngle: System.Windows.Forms.ComboBox
    // Field: label9: System.Windows.Forms.Label
    // Field: CboSubsection: System.Windows.Forms.ComboBox
    // Field: label10: System.Windows.Forms.Label
    // Field: CboPitch: System.Windows.Forms.ComboBox
    // Field: label11: System.Windows.Forms.Label
    // Field: CboTranRatio: System.Windows.Forms.ComboBox
    // Field: label12: System.Windows.Forms.Label
    // Field: CboTravel: System.Windows.Forms.ComboBox
    // Field: label13: System.Windows.Forms.Label
    // Field: CboNegaTravel: System.Windows.Forms.ComboBox
    // Field: label14: System.Windows.Forms.Label
    // Field: CboPosiTravel: System.Windows.Forms.ComboBox
    // Field: label15: System.Windows.Forms.Label
    // Field: GrdParam: System.Windows.Forms.GroupBox
    // Field: BtnClose: System.Windows.Forms.Button
    // Field: BtnOk: System.Windows.Forms.Button
    // Field: CboSpeed: System.Windows.Forms.ComboBox
    // Field: timer1: System.Windows.Forms.Timer
    // Field: label2: System.Windows.Forms.Label
    // Field: SCPort: System.IO.Ports.SerialPort
    // Field: scrollPosition: System.Drawing.Point
    // Field: deviceDpi: System.Int32
}


// Type: <PrivateImplementationDetails>
public class <PrivateImplementationDetails>
{
    // Method: Equals() -> System.Boolean
    // Method: GetHashCode() -> System.Int32
    // Method: Finalize() -> System.Void
    // Method: GetType() -> System.Type
    // Method: MemberwiseClone() -> System.Object
    // Method: ToString() -> System.String
    // Field: 6792D46EC7C4B38E9D71069E70F83D582CDB6FBDCE8CF6E275CD41546855DB2E: <PrivateImplementationDetails>+__StaticArrayInitTypeSize=16
}


// Type: <PrivateImplementationDetails>+__StaticArrayInitTypeSize=16
public __StaticArrayInitTypeSize=16
{
    // Method: Equals() -> System.Boolean
    // Method: ToString() -> System.String
    // Method: GetHashCode() -> System.Int32
    // Method: Finalize() -> System.Void
    // Method: GetType() -> System.Type
    // Method: MemberwiseClone() -> System.Object
}
