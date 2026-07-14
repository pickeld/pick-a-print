from django import forms
from django.contrib.auth.forms import AuthenticationForm

from django.utils.text import slugify

from library.collection_icons import DEFAULT_COLLECTION_ICON, is_valid_collection_icon
from library.models import NO_COLLECTION_SLUG, Collection, ModelStatus, SavedModel


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Username", "autocomplete": "username"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "autocomplete": "current-password"}),
    )


class UploadModelForm(forms.Form):
    file = forms.FileField(
        label="Model file",
        widget=forms.FileInput(
            attrs={"accept": ".stl,.3mf,model/stl,model/3mf", "required": True},
        ),
    )
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Optional custom title"}),
    )
    tag_names = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "benchy, tools"}),
        label="Tags",
    )
    collections = forms.ModelMultipleChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["collections"].queryset = Collection.objects.filter(user=user)


class SaveModelForm(forms.Form):
    url = forms.URLField(
        max_length=2000,
        widget=forms.URLInput(attrs={"placeholder": "https://www.printables.com/model/...", "autofocus": True}),
        label="Model URL",
    )
    tag_names = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "benchy, tools, gifts"}),
        label="Tags",
        help_text="Comma-separated",
    )
    collections = forms.ModelMultipleChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Add to collections",
    )
    status = forms.ChoiceField(
        choices=ModelStatus.choices,
        initial=ModelStatus.SAVED,
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["collections"].queryset = Collection.objects.filter(user=user)


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ["name", "icon", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Christmas gifts", "autocomplete": "off"}),
            "icon": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"placeholder": "Optional description", "rows": 3}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"]
        if slugify(name) == NO_COLLECTION_SLUG:
            raise forms.ValidationError("That name is reserved.")
        return name

    def clean_icon(self):
        icon = (self.cleaned_data.get("icon") or DEFAULT_COLLECTION_ICON).strip().lower()
        if not is_valid_collection_icon(icon):
            raise forms.ValidationError("Choose a valid icon.")
        return icon


class ModelUpdateForm(forms.ModelForm):
    tag_names = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "benchy, tools"}),
        label="Tags",
    )
    collections = forms.ModelMultipleChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = SavedModel
        fields = ["title", "designer", "license", "status"]
        widgets = {
            "title": forms.TextInput(),
            "designer": forms.TextInput(),
            "license": forms.TextInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["collections"].queryset = Collection.objects.filter(user=user)
        if self.instance and self.instance.pk:
            self.fields["tag_names"].initial = ", ".join(
                self.instance.tags.order_by("name").values_list("name", flat=True)
            )
            self.fields["collections"].initial = self.instance.collections.all()

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._save_tags_and_collections(instance)
        return instance

    def _save_tags_and_collections(self, instance):
        from library.models import Tag

        raw_tags = self.cleaned_data.get("tag_names", "")
        tags = []
        for name in raw_tags.split(","):
            clean = name.strip()
            if not clean:
                continue
            tag, _ = Tag.objects.get_or_create(user=instance.user, name=clean)
            tags.append(tag)
        instance.tags.set(tags)
        instance.collections.set(self.cleaned_data.get("collections", []))


class SearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.SearchInput(attrs={"placeholder": "Search models, tags, designers..."}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(ModelStatus.choices),
    )
    source_site = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "printables, makerworld..."}),
        label="Source",
    )


class ScanUploadForm(forms.Form):
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Optional scan title"}),
    )
    tag_names = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "scan, figurine"}),
        label="Tags (applied when saving to library)",
    )
    collections = forms.ModelMultipleChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Collections (when saving to library)",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["collections"].queryset = Collection.objects.filter(user=user)
