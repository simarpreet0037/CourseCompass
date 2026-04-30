from django import forms

class CourseForm(forms.Form):
    code = forms.CharField(label="Course Code", max_length=20)
    title = forms.CharField(label="Course Title", max_length=255)
    credits = forms.IntegerField(label="Credits")
    level = forms.IntegerField(label="Level")
    description = forms.CharField(
        label="Description",
        widget=forms.Textarea(attrs={'rows': 4, 'cols': 50}),
        required=False
    )

    def clean_code(self):
        """Normalize course code by removing spaces and converting to uppercase."""
        code = self.cleaned_data.get('code', '')
        # Remove spaces and convert to uppercase (e.g., 'CS 115' -> 'CS115')
        return code.replace(' ', '').strip().upper()