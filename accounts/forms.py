from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=False, label='Email Address')
    gender = forms.ChoiceField(
        choices=[('', 'Select gender')] + UserProfile.GENDER_CHOICES,
        required=False, label='Gender'
    )
    age = forms.IntegerField(
        required=False, label='Age',
        min_value=5, max_value=120,
        widget=forms.NumberInput(attrs={'placeholder': 'Your age'})
    )
    city = forms.CharField(
        required=False, label='City / Location',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. New York'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                gender=self.cleaned_data.get('gender', ''),
                age=self.cleaned_data.get('age'),
                city=self.cleaned_data.get('city', ''),
            )
        return user
